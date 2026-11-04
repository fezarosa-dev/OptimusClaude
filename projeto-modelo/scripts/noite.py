#!/usr/bin/env python3
"""Modo noturno: roda a fila do TASKS.md sozinho até esvaziar, uma tarefa por sessão nova do Claude (contexto limpo).

Uso (na raiz do projeto, na dev atualizada):  python3 scripts/noite.py
  NOITE_MODELO=opus   modelo da sessão orquestradora (padrão: o do seu settings)
  NOITE_PROMPT=...    arquivo com um prompt próprio no lugar do padrão
  NTFY_TOPICO=...     tópico do ntfy.sh que recebe o resumo no fim

Cada rodada abre `claude -p --dangerously-skip-permissions` (tudo liberado) com uma guarda que só vale esta noite
(scripts/noite_guarda.py, passada por --settings): sem push, sem PR, sem tocar na main, sem reset --hard. Os hooks
do seu ~/.claude continuam valendo. A sessão pega a primeira tarefa `aprovada` sem dúvida aberta, faz pelo fluxo do
método (worktree, TDD por subagente, revisão, correção até 3 rodadas, bateria), junta na dev LOCAL e atualiza o
TASKS.md. Tarefa que não fica verde vai para o duvidas.md e a fila segue. Sem limite de tarefas nem de horas: para
quando a fila esvazia, quando a mesma tarefa volta duas vezes seguidas ou depois de 3 falhas seguidas do claude.
No fim manda o resumo para o ntfy (NTFY_TOPICO), se estiver definido. Log em .noite/AAAA-MM-DD.log.
Só biblioteca padrão; roda em Linux e Windows.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

PROMPT_PADRAO = """Modo noturno do OptimusClaude. Você está sozinho: o usuário está dormindo, não pergunte nada a ele e não use a skill grilling. Siga o CLAUDE.md do projeto e o global.
1. Leia TASKS.md e duvidas.md só para escolher. Escolha a PRIMEIRA tarefa com estado `aprovada` (de cima para baixo) que não tenha dúvida aberta no duvidas.md. Se não houver nenhuma, responda só a linha: NOITE_FIM
2. Marque a tarefa como `em andamento (noite)` no TASKS.md.
3. Monte o brief com `python3 scripts/tarefa.py <Tn>` (só a seção da tarefa; não releia o TASKS.md inteiro). Faça a tarefa pelo fluxo do método: worktree próprio a partir da dev, implementação com TDD por subagente, revisão do diff por outro subagente, correção até 3 rodadas, bateria do que mudou (python3 scripts/testar_como_o_ci.py). Leia registros/padroes.md antes e junte nele as lições do revisor.
4. Verde: commit na branch da tarefa (mensagem pela skill commit-curto), merge --no-ff na dev LOCAL (sem push), apague o worktree, estado `feita na dev (noite, sem push)`. Depois rode `python3 scripts/arquivar.py` e commite na dev o TASKS.md, o duvidas.md, docs/ e registros/ (`chore(tarefas): <Tn> feita (noite)`): a dev tem de terminar limpa, senão a próxima noite não começa.
5. Não ficou verde depois de 3 rodadas, ou precisa de decisão do usuário: registre no duvidas.md (o que travou, onde parou, opções com recomendação), estado `travada (noite)`, deixe a branch como está, volte para a dev e commite o TASKS.md e o duvidas.md (`chore(tarefas): <Tn> travada (noite)`).
6. Nunca: push, PR, tocar na main, reset --hard (uma guarda nega).
Termine com UMA linha, a última da resposta: NOITE_TAREFA <Tn> <feita|travada> <resumo de uma frase>"""


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def sair(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def main():
    r = git("rev-parse", "--show-toplevel")
    if r.returncode != 0:
        sair("rode dentro do repositório")
    raiz = r.stdout.strip()
    os.chdir(raiz)
    if not os.path.isfile("TASKS.md"):
        sair("sem TASKS.md na raiz: o modo noturno lê a fila dele")
    claude = shutil.which("claude")
    if not claude:
        sair("claude não encontrado no PATH")
    if git("branch", "--show-current").stdout.strip() != "dev":
        sair("comece na dev (git switch dev && git pull)")
    if git("diff", "--quiet").returncode or git("diff", "--cached", "--quiet").returncode:
        sair("a dev tem mudança não commitada: commite ou guarde antes")

    if os.path.isdir(".githooks"):
        git("config", "core.hooksPath", ".githooks")  # commit fora do padrão é recusado também à noite
    os.makedirs(".noite", exist_ok=True)
    # ignora o log só nesta máquina (.git/info/exclude): mexer no .gitignore sujaria a dev e travaria a próxima noite
    exclude = os.path.join(git("rev-parse", "--git-path", "info/exclude").stdout.strip() or ".git/info/exclude")
    try:
        with open(exclude, encoding="utf-8") as f:
            ignorado = ".noite/" in f.read().splitlines()
    except OSError:
        ignorado = False
    if not ignorado:
        os.makedirs(os.path.dirname(exclude), exist_ok=True)
        with open(exclude, "a", encoding="utf-8") as f:
            f.write(".noite/\n")
    log = os.path.join(".noite", time.strftime("%Y-%m-%d") + ".log")
    guarda = os.path.join(raiz, "scripts", "noite_guarda.py")
    fd, config = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": f'"{sys.executable}" "{guarda}"'}]}]}}, f)
    try:
        laco(claude, config, log)
    finally:
        os.unlink(config)


def laco(claude, config, log):
    prompt = PROMPT_PADRAO
    if os.environ.get("NOITE_PROMPT"):
        with open(os.environ["NOITE_PROMPT"], encoding="utf-8") as f:
            prompt = f.read()
    modelo = ["--model", os.environ["NOITE_MODELO"]] if os.environ.get("NOITE_MODELO") else []

    def say(msg):
        linha = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(linha, flush=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(linha + "\n")

    feitas, travadas, anterior, falhas, motivo_fim = [], [], "", 0, "fila vazia"
    say(f"início, dev em {git('rev-parse', '--short', 'HEAD').stdout.strip()}")
    while True:
        with open(log, "a", encoding="utf-8") as lg:
            p = subprocess.run([claude, "-p", "--dangerously-skip-permissions", "--settings", config, *modelo],
                               input=prompt, stdout=subprocess.PIPE, stderr=lg, text=True, encoding="utf-8", errors="replace")
            lg.write(p.stdout + "\n")
        achadas = re.findall(r"^NOITE_(?:FIM|TAREFA).*$", p.stdout, re.M)
        if p.returncode != 0 or not achadas:
            falhas += 1
            say(f"rodada sem resposta válida (saída {p.returncode}), falha {falhas} de 3")
            if falhas >= 3:
                motivo_fim = "3 falhas seguidas do claude (veja o log)"
                break
            continue
        falhas = 0
        ultima = achadas[-1]
        if ultima == "NOITE_FIM":
            break
        partes = (ultima.split(None, 3) + ["", "", ""])[1:4]
        tn, estado, resto = partes
        say(f"{tn} {estado}: {resto}")
        if tn == anterior:
            motivo_fim = f"{tn} voltou duas vezes seguidas"
            break
        anterior = tn
        (feitas if estado == "feita" else travadas).append(tn)
        if git("branch", "--show-current").stdout.strip() != "dev":
            git("switch", "-q", "dev")

    # rede de segurança: arquivo de estado que a sessão esqueceu de commitar entra num commit, para a próxima noite
    # começar com a dev limpa. Só esses caminhos; qualquer outra sobra fica para você ver de manhã.
    estado = ["TASKS.md", "duvidas.md", "docs", "registros"]
    if git("status", "--porcelain", "--", *estado).stdout.strip() and git("branch", "--show-current").stdout.strip() == "dev":
        git("add", "--", *[c for c in estado if os.path.exists(c)])
        if git("commit", "-m", "chore(tarefas): estado da noite").returncode == 0:
            say("arquivos de estado esquecidos commitados na dev")
    resumo = (f"Noite: {len(feitas)} feita(s) {' '.join(feitas)} · {len(travadas)} travada(s) {' '.join(travadas)}"
              f" · fim: {motivo_fim}. Push da dev: você decide.")
    say(resumo)
    topico = os.environ.get("NTFY_TOPICO")
    if topico:
        req = urllib.request.Request(f"https://ntfy.sh/{topico}", data=resumo.encode("utf-8"),
                                     headers={"Title": "Modo noturno terminou", "Tags": "crescent_moon"})
        try:
            urllib.request.urlopen(req, timeout=15).close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
