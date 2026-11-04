#!/usr/bin/env python3
"""Brief de uma tarefa sem ler o TASKS.md inteiro: a seção da Tn e as dúvidas abertas dela no duvidas.md.

    python3 scripts/tarefa.py T7      # seção da T7 + dúvidas abertas que citam a T7 (saída 1 se não existir)
    python3 scripts/tarefa.py         # lista das tarefas que ainda não estão no ar: "Tn · título · estado"

Só biblioteca padrão. Lê da raiz do repositório (ou do diretório atual, fora de um repositório git).
"""
import re
import subprocess
import sys
from pathlib import Path


def secoes(texto):
    """[(cabeçalho, texto da seção)] de cada '### ' até o próximo '## ' ou '### '."""
    out, atual, cerca = [], None, False
    for linha in texto.splitlines(keepends=True):
        if linha.lstrip().startswith(("```", "~~~")):
            cerca = not cerca
        if cerca or linha.lstrip().startswith(("```", "~~~")):
            if atual is not None:
                atual[1].append(linha)
            continue
        if linha.startswith("### "):
            atual = [linha.rstrip("\n"), [linha]]
            out.append(atual)
        elif linha.startswith("## ") or linha.startswith("# "):
            atual = None
        elif atual is not None:
            atual[1].append(linha)
    return [(c, "".join(t).rstrip() + "\n") for c, t in out]


def _ler(caminho):
    try:
        return Path(caminho).read_text(encoding="utf-8")
    except OSError:
        return ""


def _id(cabecalho):
    m = re.match(r"### (T\d+)\b", cabecalho)
    return m.group(1) if m else None


def _estado(texto):
    m = re.search(r"\*\*Estado:\*\*\s*(.+)", texto)
    return m.group(1).strip() if m else ""


def respondida(texto):
    return re.search(r"\*\*Resposta\b", texto) is not None


def brief(raiz, tn):
    tn = tn.upper()
    achada = [t for c, t in secoes(_ler(Path(raiz) / "TASKS.md")) if _id(c) == tn]
    if not achada:
        return None
    citam = re.compile(rf"\b{re.escape(tn)}\b")
    duvidas = [t for c, t in secoes(_ler(Path(raiz) / "duvidas.md")) if citam.search(t) and not respondida(t)]
    partes = [achada[0]]
    if duvidas:
        partes.append("Dúvidas abertas desta tarefa (duvidas.md):\n\n" + "\n".join(duvidas))
    return "\n".join(partes)


def abertas(raiz):
    out = []
    for c, t in secoes(_ler(Path(raiz) / "TASKS.md")):
        tn, estado = _id(c), _estado(t)
        if tn and "no ar" not in estado:
            titulo = c.split("·", 1)[1].strip() if "·" in c else c[4:].strip()
            out.append(f"{tn} · {titulo} · {estado}")
    return out


def raiz_repo():
    p = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(p.stdout.strip()) if p.returncode == 0 else Path.cwd()


def main(argv):
    raiz = raiz_repo()
    if len(argv) < 2:
        print("\n".join(abertas(raiz)) or "nenhuma tarefa aberta")
        return 0
    txt = brief(raiz, argv[1])
    if txt is None:
        print(f"{argv[1]} não está no TASKS.md", file=sys.stderr)
        return 1
    print(txt, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
