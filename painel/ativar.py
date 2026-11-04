#!/usr/bin/env python3
"""Aponta o painel para o projeto do diretório dado (cwd da sessão) e o liga. Uso: ativar.py <cwd>"""
import json, os, re, signal, subprocess, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(AQUI, "config.json")


def nome_sessoes(caminho):
    # o Claude Code nomeia a pasta de sessões trocando todo caractere não alfanumérico por "-"
    return re.sub(r"[^A-Za-z0-9]", "-", caminho)


def projeto_de(cwd):
    if not os.path.isdir(cwd):
        raise ValueError(f"diretório não existe: {cwd}")
    cwd = os.path.realpath(cwd)
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True)
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else cwd


def novo_config(cfg, projeto, home=None, uid=None):
    home = home or os.path.expanduser("~")
    uid = os.getuid() if uid is None else uid
    nome = nome_sessoes(projeto)
    novo = dict(cfg)
    novo.update({
        "projeto": projeto,
        # pasta dos worktrees, relativa ao projeto (padrão: a irmã ../wt); se não existir, nenhum worktree casa (fontes.py usa startswith)
        "worktrees": os.path.normpath(os.path.join(projeto, cfg.get("worktrees_relativo") or "../wt")),
        "sessoes": os.path.join(home, ".claude", "projects", nome),
        "saidas": f"/tmp/claude-{uid}/{nome}",
        "sessao": None,
    })
    return novo


def gravar(cfg):
    tmp = CONFIG + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, CONFIG)


def main(cwd):
    projeto = projeto_de(cwd)
    # primeira vez: parte do config.example.json
    with open(CONFIG if os.path.exists(CONFIG) else os.path.join(AQUI, "config.example.json")) as f:
        atual = json.load(f)
    novo = novo_config(atual, projeto)
    if novo != atual:
        gravar(novo)
        try:
            with open(os.path.join(AQUI, "servidor.pid")) as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):  # espera sair, senão o iniciar.py acha o antigo "já no ar"
                time.sleep(0.25)
                os.kill(pid, 0)
        except (OSError, ValueError):
            pass
    return subprocess.run([sys.executable, os.path.join(AQUI, "iniciar.py")]).returncode


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("uso: ativar.py <diretório da sessão>")
    try:
        sys.exit(main(sys.argv[1]))
    except ValueError as e:
        sys.exit(str(e))
