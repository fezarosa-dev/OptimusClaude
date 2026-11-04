#!/usr/bin/env python3
"""Quanto entra em toda sessão antes de você digitar nada, em tokens estimados (só biblioteca padrão).

    python3 ~/.claude/scripts/orcamento_contexto.py [pasta-do-projeto] [--limite 10000]

Soma o que o Claude Code carrega sempre: o CLAUDE.md global e os do projeto (a pasta e as de cima, mais
CLAUDE.local.md), cada arquivo importado com @ (seguindo os imports, sem entrar em ciclo), as primeiras 200 linhas do
MEMORY.md da memória automática do projeto e o nome + descrição de cada skill em ~/.claude/skills (o corpo da skill só
entra quando ela é usada). Mostra os maiores primeiro e avisa acima do limite. O custo dos plugins ligados:
plugin_audit.py. Não conta: rules/ (~/.claude/rules e .claude/rules), skills de projeto e de plugin, e @ no meio
da linha. Estimativa: 1 token a cada ~3,5 caracteres (português); serve para comparar, não para cobrar.
"""
import argparse
import math
import re
import sys
from pathlib import Path

CHARS_POR_TOKEN = 3.5
LINHAS_MEMORIA = 200


def tokens(texto):
    return math.ceil(len(texto) / CHARS_POR_TOKEN)


def _ler(p):
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _com_imports(arquivo, vistos, itens):
    arquivo = Path(arquivo).expanduser().resolve()
    if arquivo in vistos:
        return
    texto = _ler(arquivo)
    if texto is None:
        return
    vistos.add(arquivo)
    itens.append((str(arquivo), tokens(texto)))
    for m in re.finditer(r"^@(\S+)", texto, re.MULTILINE):
        alvo = Path(m.group(1)).expanduser()
        _com_imports(alvo if alvo.is_absolute() else arquivo.parent / alvo, vistos, itens)


def _pasta_memoria(home, proj):
    base = Path(home) / ".claude" / "projects"
    s = str(Path(proj).resolve())
    for nome in (re.sub(r"[^A-Za-z0-9]", "-", s), s.replace("/", "-").replace("\\", "-")):
        if (base / nome).is_dir():
            return base / nome / "memory"
    return None


def _descricao_skill(texto):
    m = re.match(r"---\n(.*?)\n---", texto, re.DOTALL)
    return m.group(1) if m else texto[:300]


def medir(home, proj):
    """[(fonte, tokens)] do que entra em toda sessão."""
    home, proj = Path(home), Path(proj).resolve()
    itens, vistos = [], set()
    _com_imports(home / ".claude" / "CLAUDE.md", vistos, itens)
    pastas = [proj, *proj.parents]
    for pasta in reversed(pastas):
        if pasta == home / ".claude":
            continue
        for nome in ("CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md"):
            _com_imports(pasta / nome, vistos, itens)
    mem = _pasta_memoria(home, proj)
    if mem:
        texto = _ler(mem / "MEMORY.md")
        if texto:
            itens.append((str(mem / "MEMORY.md"), tokens("".join(texto.splitlines(True)[:LINHAS_MEMORIA]))))
    for skill in sorted((home / ".claude" / "skills").glob("*/SKILL.md")):
        texto = _ler(skill)
        if texto:
            itens.append((f"skills/{skill.parent.name}", tokens(_descricao_skill(texto))))
    return itens


def relatorio(itens, limite=10_000):
    arquivos = sorted((i for i in itens if not i[0].startswith("skills/")), key=lambda i: -i[1])
    skills = [i for i in itens if i[0].startswith("skills/")]
    total = sum(t for _, t in itens)
    linhas = [f"{t:>7}  {n}" for n, t in arquivos]
    if skills:
        maiores = ", ".join(f"{n[7:]} {t}" for n, t in sorted(skills, key=lambda i: -i[1])[:5])
        linhas.append(f"{sum(t for _, t in skills):>7}  descrições de {len(skills)} skills (maiores: {maiores})")
    linhas.append(f"{total:>7}  TOTAL estimado por sessão (sem plugins: veja plugin_audit.py)")
    if total > limite:
        linhas.append(f"ACIMA do limite de {limite}: encurte o maior arquivo, mova detalhe para docs/ lidos sob demanda "
                      "ou desligue skills que não usa.")
    return "\n".join(linhas)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("projeto", nargs="?", default=".")
    ap.add_argument("--limite", type=int, default=10_000)
    a = ap.parse_args()
    print(relatorio(medir(Path.home(), a.projeto), a.limite))
    return 0


if __name__ == "__main__":
    sys.exit(main())
