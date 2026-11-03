"""Gera e confere registros/INDICE.md: cada arquivo de registros/ com o sha256.

    python3 scripts/registros/indice.py [pasta]             # regenera
    python3 scripts/registros/indice.py --conferir [pasta]  # sai com 1 se o índice não bate com o que o git tem

Regenerar lista tudo o que está no disco. Conferir olha só os arquivos rastreados pelo git (o resumo de bateria ainda não
commitado não reprova); fora de um repositório, confere a pasta inteira. Só biblioteca padrão. O índice não lista a si mesmo.
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

NOME = "INDICE.md"
PADRAO = Path(__file__).resolve().parents[2] / "registros"
CABECALHO = """# Índice dos registros

Gerado por `scripts/registros/indice.py`: não edite à mão. Cada linha é um arquivo desta pasta com o sha256 dele
(`sha256sum <arquivo>` confere).

| Arquivo | sha256 |
|---|---|
"""


def gerar(pasta) -> str:
    pasta = Path(pasta)
    arquivos = sorted(p for p in pasta.rglob("*") if p.is_file() and p.relative_to(pasta).as_posix() != NOME)
    linhas = [f"| `{p.relative_to(pasta).as_posix()}` | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |\n" for p in arquivos]
    return CABECALHO + "".join(linhas)


def escrever(pasta) -> Path:
    destino = Path(pasta) / NOME
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(gerar(pasta), encoding="utf-8")
    return destino


def conferir(pasta) -> bool:
    destino = Path(pasta) / NOME
    return destino.is_file() and destino.read_text(encoding="utf-8") == gerar(pasta)


def rastreados(pasta):
    """Caminhos (relativos à pasta) que o git rastreia, ou None se a pasta não está num repositório."""
    try:
        saida = subprocess.run(["git", "ls-files", "-z", "--", "."], cwd=pasta, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return sorted(c for c in saida.decode("utf-8", "surrogateescape").split("\0") if c and c != NOME)


def problemas(pasta):
    """O que está errado no índice, em frases. Lista vazia = em dia."""
    pasta = Path(pasta)
    lista = rastreados(pasta)
    if lista is None:
        return [] if conferir(pasta) else [f"{NOME} não bate com os arquivos de {pasta}"]
    destino = pasta / NOME
    if not destino.is_file():
        return [f"falta {NOME}"]
    linhas = dict(re.findall(r"(?m)^\| `([^`]+)` \| `([0-9a-f]{64})` \|$", destino.read_text(encoding="utf-8")))
    achados = []
    for caminho in lista:
        atual = hashlib.sha256((pasta / caminho).read_bytes()).hexdigest() if (pasta / caminho).is_file() else None
        if caminho in linhas and linhas[caminho] != atual:
            achados.append(f"{caminho}: sha256 do índice não bate com o arquivo")
        elif caminho not in linhas and not caminho.startswith("baterias/"):
            achados.append(f"{caminho}: rastreado e fora do índice")
    achados += [f"{c}: o índice lista, mas o arquivo não existe" for c in linhas if not (pasta / c).is_file()]
    return achados


USO = "uso: indice.py [--conferir] [pasta]"


def principal(args):
    if "--help" in args or "-h" in args:
        print(USO)
        return 0
    desconhecida = [a for a in args if a.startswith("-") and a != "--conferir"]
    if desconhecida:
        print(f"opção desconhecida: {desconhecida[0]}\n{USO}", file=sys.stderr)
        return 2
    resto = [a for a in args if a != "--conferir"]
    pasta = Path(resto[0]) if resto else PADRAO
    if "--conferir" in args:
        achados = problemas(pasta)
        for a in achados:
            print(a, file=sys.stderr)
        if achados:
            print(f"{pasta / NOME} desatualizado: rode python3 scripts/registros/indice.py", file=sys.stderr)
        return 1 if achados else 0
    print(escrever(pasta))
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
