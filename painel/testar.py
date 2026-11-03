#!/usr/bin/env python3
"""Roda só os testes do painel ligados ao que mudou.

  python3 testar.py                 # diff contra HEAD + não commitado + arquivos novos
  python3 testar.py --base dev      # o que mudou desde que a branch saiu da dev
  python3 testar.py a.py b.js       # só estes arquivos
  python3 testar.py --tudo          # todos os testes
  python3 testar.py --so-decidir    # mostra o que rodaria, sem rodar

Um teste está ligado a um arquivo se o importa (direta ou indiretamente) ou cita o nome dele.
Arquivo mudado que nenhum teste alcança (fora .md e .gitignore) roda tudo: melhor sobrar que faltar.
"""
import argparse
import ast
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
IGNORAR = {".gitignore"}


def imports_locais(arq, modulos):
    nomes = set()
    for no in ast.walk(ast.parse(arq.read_text(), str(arq))):
        if isinstance(no, ast.Import):
            nomes |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module and not no.level:
            nomes.add(no.module.split(".")[0])
    return nomes & modulos


def ligados(arq_teste, mudados, deps):
    """Arquivos mudados que o teste alcança, por import transitivo ou citação do nome."""
    vistos, pilha = set(), [arq_teste.stem]
    while pilha:
        m = pilha.pop()
        if m not in vistos:
            vistos.add(m)
            pilha += deps.get(m, ())
    texto = "\n".join((AQUI / f"{m}.py").read_text() for m in vistos)
    return {f for f in mudados if Path(f).stem in vistos or f in texto}


def escolher(mudados):
    """Devolve (arquivos de teste a rodar, motivo)."""
    testes = sorted(AQUI.glob("test_*.py"))
    mudados = {Path(f).name for f in mudados if Path(f).name not in IGNORAR and not f.endswith(".md")}
    apagados = sorted(f for f in mudados if not (AQUI / f).exists())
    if apagados:
        return testes, f"apagado, roda tudo: {', '.join(apagados)}"
    modulos = {f.stem for f in AQUI.glob("*.py")}
    deps = {f.stem: imports_locais(f, modulos) for f in AQUI.glob("*.py")}
    por_teste = {t: ligados(t, mudados, deps) for t in testes}
    sem_teste = sorted(mudados - set().union(set(), *por_teste.values()))
    if sem_teste:
        return testes, f"sem teste ligado, roda tudo: {', '.join(sem_teste)}"
    return [t for t in testes if por_teste[t]], f"mudou: {', '.join(sorted(mudados)) or 'nada'}"


def mudados_no_git(base):
    def git(*a):
        r = subprocess.run(["git", *a], cwd=AQUI, capture_output=True, text=True, check=True)
        return r.stdout.split("\n")
    # desde o ponto em que a branch saiu da base: o que entrou só na base não conta
    ponto = git("merge-base", base, "HEAD")[0]
    nomes = git("diff", "--name-only", "--relative", ponto) + git("ls-files", "--others", "--exclude-standard")
    return {n for n in nomes if n and "/" not in n}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("arquivos", nargs="*")
    p.add_argument("--base", default="HEAD")
    p.add_argument("--tudo", action="store_true")
    p.add_argument("--so-decidir", action="store_true")
    a = p.parse_args(argv)

    if a.tudo:
        escolhidos, motivo = sorted(AQUI.glob("test_*.py")), "--tudo"
    else:
        escolhidos, motivo = escolher(a.arquivos or mudados_no_git(a.base))

    total = len(list(AQUI.glob("test_*.py")))
    print(f"[testar] {motivo}")
    print(f"[testar] {len(escolhidos)}/{total} arquivos de teste: {' '.join(t.stem for t in escolhidos) or '-'}")
    if a.so_decidir or not escolhidos:
        return 0
    cmd = [sys.executable, "-m", "unittest", "-q", *(t.stem for t in escolhidos)]
    return subprocess.run(cmd, cwd=AQUI).returncode


if __name__ == "__main__":
    sys.exit(main())
