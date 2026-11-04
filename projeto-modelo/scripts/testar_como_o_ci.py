"""Roda na máquina o que o CI rodaria para o que mudou, pelo MESMO mapa do CI (scripts/o_que_testar.py).
Serve para juntar na dev (que não roda CI) e para preparar o PR para a main sem o PR ser o primeiro lugar
onde um teste roda. Só biblioteca padrão; roda em Linux, macOS e Windows.

    python3 scripts/testar_como_o_ci.py [base]              # base padrão: dev. O diff base...HEAD, mais o que não
                                                            # foi commitado e os arquivos novos não rastreados
    ARQUIVOS=lista.txt python3 scripts/testar_como_o_ci.py  # só estes arquivos (um por linha): a volta depois de um conserto
    EXIGIR_TUDO=1 python3 scripts/testar_como_o_ci.py       # todas as verificações; PULADO também reprova (antes do PR)
    SO_DECIDIR=1 python3 scripts/testar_como_o_ci.py        # só mostra os arquivos e os passos; não roda nada
    REGISTRO=0 python3 scripts/testar_como_o_ci.py          # não grava o registro da rodada (o CI usa)

Não para na primeira falha: roda todos os passos e marca OK, FALHOU ou PULADO (programa que falta).
Cada rodada deixa um resumo em registros/baterias/ (data, branch, commit, árvore, passos, duração e o sha256 do
log) e o log completo comprimido FORA do repositório, em REGISTROS_FORA (padrão ~/.local/share/registros-de-garantia).
Sai com 1 se algo falhar (ou, com EXIGIR_TUDO=1, se algo ficar PULADO); 2 se não houver repositório ou base.
Os comandos das verificações vêm do o_que_testar.py e rodam no shell da plataforma.
"""
import gzip
import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def git(*args, check=True):
    """Saída (bytes) de um comando git; levanta CalledProcessError se falhar e check=True."""
    return subprocess.run(["git", *args], capture_output=True, check=check).stdout


def texto(*args):
    return git(*args).decode("utf-8", "surrogateescape").strip()


def decidir(*args):
    """Roda o mapa (o_que_testar.py) e devolve as linhas da saída. O aviso do mapa vai direto ao stderr."""
    saida = subprocess.run([sys.executable, "-I", "scripts/o_que_testar.py", *args], stdout=subprocess.PIPE, check=True)
    return saida.stdout.decode("utf-8").splitlines()


def quais_mudaram(base):
    nomes = set()
    for cmd in (["diff", "-z", "--name-only", "--no-renames", f"{base}...HEAD"],
                ["diff", "-z", "--name-only", "--no-renames", "HEAD"],
                ["ls-files", "-z", "--others", "--exclude-standard"]):
        nomes.update(n.decode("utf-8", "surrogateescape") for n in git(*cmd).split(b"\0") if n)
    return sorted(nomes)


def rodar(passos, resultados, emitir):
    for passo in passos:
        programas, _, comando = decidir("--mostrar", passo)[0].partition("\t")
        falta = "".join(f" {p}" for p in programas.split() if not shutil.which(p))
        if falta:
            resultados.append((passo, f"PULADO (falta:{falta})"))
            emitir(f"== {passo}: PULADO, falta:{falta}\n")
            continue
        emitir(f"== {passo}: {comando}\n")
        # shell=True só aqui: o comando é do mapa e pode usar &&, pipes, cd...
        proc = subprocess.Popen(comando, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            for linha in proc.stdout:
                emitir(linha)
            proc.wait()
        except BaseException:
            proc.kill()
            raise
        resultados.append((passo, "OK" if proc.returncode == 0 else "FALHOU"))


def registrar(veredito, raiz, base, mudados, resultados, log, inicio):
    if os.environ.get("REGISTRO", "1") == "0":
        return
    agora = datetime.now().astimezone()
    branch = texto("rev-parse", "--abbrev-ref", "HEAD")
    nome = f"{agora:%Y-%m-%d-%H%M%S}-{re.sub(r'[^A-Za-z0-9._-]', '-', branch)}"
    casa = str(Path.home())
    fora = Path(os.environ.get("REGISTROS_FORA") or Path(casa) / ".local/share/registros-de-garantia") / raiz.name / "baterias"
    fora.mkdir(parents=True, exist_ok=True)
    (raiz / "registros" / "baterias").mkdir(parents=True, exist_ok=True)
    arq_log = fora / f"{nome}.log.gz"
    arq_log.write_bytes(gzip.compress(bytes(log)))
    sujo = "não"
    if git("status", "--porcelain", "--", ".", ":(exclude)registros").strip():
        novos = len([n for n in git("ls-files", "--others", "--exclude-standard", "--", ".", ":(exclude)registros").split(b"\n") if n])
        diff = git("diff", "--no-ext-diff", "--no-color", "--binary", "HEAD", "--", ".", ":(exclude)registros")
        sujo = f"sim (sha256 do git diff: {hashlib.sha256(diff).hexdigest()}; arquivos novos não rastreados: {novos})"
    shown = str(arq_log)
    if shown.startswith(casa):
        shown = "~" + shown[len(casa):]
    linhas = [
        f"# Bateria {nome}", "",
        f"- **Data:** {agora:%Y-%m-%dT%H:%M:%S%z}",
        f"- **Branch:** `{branch}`",
        f"- **Commit:** `{texto('rev-parse', 'HEAD')}`",
        f"- **Árvore (hash):** `{texto('rev-parse', 'HEAD^{tree}')}`",
        f"- **Mudança não commitada:** {sujo}",
        f"- **Base:** `{base}` · **EXIGIR_TUDO:** {os.environ.get('EXIGIR_TUDO', '0')} · **Arquivos no diff:** {len(mudados)}",
        f"- **Resultado:** {veredito}",
        f"- **Duração:** {int(time.time() - inicio)} s",
        f"- **Log completo:** sha256 `{hashlib.sha256(arq_log.read_bytes()).hexdigest()}`, fora do repositório (`{shown}`)",
        "", "| Passo | Resultado |", "|---|---|",
        *(f"| {p} | {r} |" for p, r in resultados),
    ]
    (raiz / "registros" / "baterias" / f"{nome}.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"registro: registros/baterias/{nome}.md")


def principal(argv):
    try:
        raiz = Path(texto("rev-parse", "--show-toplevel"))
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("não é um repositório git", file=sys.stderr)
        return 2
    os.chdir(raiz)
    base = argv[0] if argv else "dev"
    exigir = os.environ.get("EXIGIR_TUDO", "0") == "1"

    # --- o que mudou e o que roda
    if exigir:
        mudados, passos = [], decidir("--tudo")
    else:
        if os.environ.get("ARQUIVOS"):
            with open(os.environ["ARQUIVOS"], encoding="utf-8") as f:
                mudados = [l.rstrip("\n") for l in f if l.strip()]
        else:
            if subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"],
                              capture_output=True).returncode != 0:
                print(f"base '{base}' não existe (git fetch?)", file=sys.stderr)
                return 2
            mudados = quais_mudaram(base)
        passos = decidir(*mudados)

    if os.environ.get("SO_DECIDIR", "0") == "1":
        print(f"Arquivos ({len(mudados)}):")
        for m in mudados:
            print(f"  {m}")
        print("Passos:")
        for p in passos:
            print(f"  {p}")
        return 0

    # --- rodar
    resultados, log, inicio = [], bytearray(), time.time()

    def emitir(dado):  # tela e log ao mesmo tempo, em bytes (a saída dos comandos pode não ser UTF-8)
        dado = dado.encode("utf-8") if isinstance(dado, str) else dado
        log.extend(dado)
        sys.stdout.flush()
        sys.stdout.buffer.write(dado)
        sys.stdout.buffer.flush()

    def _parar(*_):  # SIGTERM (kill, timeout do painel ou da noite) registra como o ctrl-C
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _parar)
    try:
        rodar(passos, resultados, emitir)
    except KeyboardInterrupt:
        registrar("INTERROMPIDA", raiz, base, mudados, resultados, log, inicio)
        return 130

    print("\nResumo:")
    largura = max((len(p) for p, _ in resultados), default=0)
    for p, r in resultados:
        print(f"{p.ljust(largura)}  {r}")
    reprova = any(r == "FALHOU" for _, r in resultados) or (exigir and any(r.startswith("PULADO") for _, r in resultados))
    if reprova:
        registrar("VERMELHA", raiz, base, mudados, resultados, log, inicio)
        print("VERMELHA: não junte.")
        return 1
    registrar("VERDE", raiz, base, mudados, resultados, log, inicio)
    print("VERDE.")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
