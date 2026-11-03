#!/usr/bin/env python3
"""Barra de status do Claude Code: contexto, uso 5h/semanal, pasta:branch, repo GitHub,
modelo/effort, tokens da sessão (com os subagentes) e tempo de API. Lê o JSON que o Claude Code manda no stdin."""
import glob
import json
import os
import re
import subprocess
import sys

RESET = '\033[0m'
CINZA = '\033[38;5;245m'


def cor_pct(pct):
    if pct < 50:
        return '\033[38;2;64;160;43m'
    if pct < 80:
        return '\033[38;2;223;142;29m'
    return '\033[38;2;210;15;57m'


def git(cwd, *args):
    try:
        r = subprocess.run(['git', '-C', cwd, '--no-optional-locks', *args],
                           capture_output=True, text=True, timeout=1)
        return r.stdout.strip() if r.returncode == 0 else ''
    except (OSError, subprocess.SubprocessError):
        return ''


def repo_github(cwd):
    m = re.search(r'github\.com[:/](.+?)(?:\.git)?/?$', git(cwd, 'remote', 'get-url', 'origin'))
    return m.group(1) if m else ''


def tokens_do_arquivo(caminho, vistos):
    # Cada mensagem pode aparecer em várias linhas (um bloco por linha) com o mesmo usage: conta uma vez por id.
    total = 0
    try:
        with open(caminho, encoding='utf-8') as f:
            for linha in f:
                if '"usage"' not in linha:
                    continue
                try:
                    msg = json.loads(linha).get('message') or {}
                except ValueError:
                    continue
                uso, mid = msg.get('usage'), msg.get('id')
                if not isinstance(uso, dict) or mid in vistos:
                    continue
                vistos.add(mid)
                total += sum(uso.get(k) or 0 for k in ('input_tokens', 'output_tokens',
                             'cache_creation_input_tokens', 'cache_read_input_tokens'))
    except OSError:
        return 0
    return total


def tokens_da_sessao(transcript):
    # Sessão + subagentes dela, que ficam em <transcript sem .jsonl>/subagents/.
    if not transcript:
        return 0
    pasta = os.path.join(os.path.splitext(transcript)[0], 'subagents')
    arquivos = [transcript, *sorted(glob.glob(os.path.join(pasta, '**', '*.jsonl'), recursive=True))]
    vistos = set()
    return sum(tokens_do_arquivo(a, vistos) for a in arquivos)


def curto(n):
    for limite, sufixo in ((1e6, 'M'), (1e3, 'k')):
        if n >= limite:
            return f'{n / limite:.1f}'.rstrip('0').rstrip('.') + sufixo
    return str(n)


def duracao(ms):
    s = int(ms // 1000)
    h, m, s = s // 3600, s % 3600 // 60, s % 60
    return f'{h}h{m:02d}m' if h else f'{m}m{s:02d}s'


def pct(rotulo, valor):
    if valor is None:
        return None
    v = int(valor)
    return f'{cor_pct(v)}{rotulo} {v}%{RESET}'


def montar(d):
    cwd = (d.get('workspace') or {}).get('current_dir') or d.get('cwd') or ''
    limites = d.get('rate_limits') or {}
    modelo = (d.get('model') or {}).get('display_name', '')
    effort = (d.get('effort') or {}).get('level', '')
    partes = [
        pct('Ctx', (d.get('context_window') or {}).get('used_percentage')),
        pct('5h', (limites.get('five_hour') or {}).get('used_percentage')),
        pct('Sem', (limites.get('seven_day') or {}).get('used_percentage')),
    ]
    if cwd:
        branch = git(cwd, 'symbolic-ref', '--short', 'HEAD') or git(cwd, 'rev-parse', '--short', 'HEAD')
        repo = repo_github(cwd)
        partes.append('📁 ' + os.path.basename(cwd))
        partes.append(f'{repo}:{branch}' if repo and branch else (f'⎇ {branch}' if branch else repo or None))
    partes.append(' · '.join(p for p in (modelo, effort) if p) or None)
    tokens = tokens_da_sessao(d.get('transcript_path') or '')
    partes.append(f'{curto(tokens)} tok' if tokens else None)
    api_ms = (d.get('cost') or {}).get('total_api_duration_ms')
    partes.append(f'⏱ {duracao(api_ms)}' if api_ms else None)
    texto = f' {CINZA}│{RESET} '.join(p for p in partes if p)
    return re.sub(r'[\x00-\x08\x0b-\x1a\x1c-\x1f\x7f]', '', texto)  # nada de controle vindo do JSON (mantém o ESC das cores)


if __name__ == '__main__':
    try:
        dados = json.load(sys.stdin)
    except ValueError:
        dados = {}
    print(montar(dados if isinstance(dados, dict) else {}))
