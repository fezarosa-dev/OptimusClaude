#!/usr/bin/env python3
"""Arquivo morto: mantém pequenos os arquivos que a sessão mais lê.

    python3 scripts/arquivar.py

- Tarefa do TASKS.md com estado "no ar" vai para docs/tarefas-feitas.md.
- Dúvida do duvidas.md com a linha **Resposta (...)** vai para docs/duvidas-resolvidas.md.
Nada se apaga: a seção sai inteira de um arquivo e entra no fim do outro. Rodar de novo não muda nada.
Roda no fim da skill publicar e de cada tarefa do modo noturno.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tarefa import _estado, _id, raiz_repo, respondida  # noqa: E402

CABECALHOS = {
    "tarefas-feitas.md": "# Tarefas feitas\n\nO que saiu do TASKS.md depois de ir para o ar (scripts/arquivar.py).\n",
    "duvidas-resolvidas.md": "# Dúvidas resolvidas\n\nO que saiu do duvidas.md depois de respondido (scripts/arquivar.py).\n",
}


def _separar(texto, sai):
    """Tira do texto as seções '### ' para as quais sai(cabeçalho, seção) é verdade. Devolve (resto, [(cab, seção)])."""
    linhas, resto, saidas, atual, cerca = texto.splitlines(keepends=True), [], [], None, False
    for linha in linhas + ["## \n"]:  # sentinela fecha a última seção
        borda = linha.lstrip().startswith(("```", "~~~"))
        if borda:
            cerca = not cerca
        if not (cerca or borda) and linha.startswith(("### ", "## ", "# ")):
            if atual is not None:
                cab, corpo = atual
                if sai(cab, "".join(corpo)):
                    saidas.append((cab, "".join(corpo).rstrip() + "\n"))
                else:
                    resto.extend(corpo)
            atual = [linha.rstrip("\n"), [linha]] if linha.startswith("### ") else None
            if atual is None and linha != "## \n":
                resto.append(linha)
        elif atual is not None:
            atual[1].append(linha)
        else:
            resto.append(linha)
    return "".join(resto), saidas


def _mover(origem, destino, sai):
    if not origem.is_file():
        return []
    resto, saidas = _separar(origem.read_text(encoding="utf-8"), sai)
    if not saidas:
        return []
    ids = []
    for c, _ in saidas:
        m = re.match(r"### ([A-Z]+-?\d+)", c)
        ids.append(m.group(1) if m else c[4:60].strip())
    destino.parent.mkdir(parents=True, exist_ok=True)
    atual = destino.read_text(encoding="utf-8") if destino.is_file() else CABECALHOS[destino.name]
    _gravar(destino, atual.rstrip() + "\n\n" + "\n".join(s for _, s in saidas))
    _gravar(origem, re.sub(r"\n{3,}", "\n\n", resto))
    return ids


def _gravar(caminho, texto):
    """Grava por arquivo temporário + os.replace: quem lê nunca vê o arquivo pela metade."""
    tmp = caminho.with_name(caminho.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, caminho)


def arquivar(raiz):
    raiz = Path(raiz)
    return {
        "tarefas": _mover(raiz / "TASKS.md", raiz / "docs" / "tarefas-feitas.md",
                          lambda c, s: bool(_id(c)) and "no ar" in _estado(s)),
        "duvidas": _mover(raiz / "duvidas.md", raiz / "docs" / "duvidas-resolvidas.md",
                          lambda c, s: respondida(s)),
    }


def main():
    m = arquivar(raiz_repo())
    print(f"arquivadas: tarefas {', '.join(m['tarefas']) or 'nenhuma'} · dúvidas {', '.join(m['duvidas']) or 'nenhuma'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
