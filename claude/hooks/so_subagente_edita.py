#!/usr/bin/env python3
"""Hook PreToolUse (Write/Edit/MultiEdit/NotebookEdit): a sessão principal não edita código; quem edita é subagente.

Só vale em projeto do método: o arquivo tem de estar sob uma pasta com TASKS.md (procurado subindo a partir do
arquivo). Fora disso, não faz nada. Subagente (o payload traz agent_id) passa sempre. A principal continua livre para
os arquivos de estado e texto: qualquer .md, e o que estiver em registros/, docs/, .claude/ ou na memória
(~/.claude). Qualquer erro: deixa passar. Desligar numa sessão: OPTIMUS_PRINCIPAL_EDITA=1."""
import json
import os
import sys

FERRAMENTAS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PASTAS_LIVRES = {"registros", "docs", ".claude"}


def raiz_do_metodo(caminho):
    d = os.path.dirname(os.path.abspath(caminho))
    while True:
        if os.path.isfile(os.path.join(d, "TASKS.md")):
            return d
        pai = os.path.dirname(d)
        if pai == d:
            return None
        d = pai


def decidir(entrada):
    """Devolve o motivo da negação, ou None para deixar passar."""
    if os.environ.get("OPTIMUS_PRINCIPAL_EDITA") == "1" or entrada.get("tool_name") not in FERRAMENTAS:
        return None
    if entrada.get("agent_id") or entrada.get("agent_type"):
        return None
    ti = entrada.get("tool_input") or {}
    caminho = ti.get("file_path") or ti.get("notebook_path")
    if not isinstance(caminho, str):
        return None
    caminho = os.path.abspath(os.path.expanduser(caminho))
    if caminho.lower().endswith(".md"):
        return None
    if caminho.startswith(os.path.join(os.path.expanduser("~"), ".claude") + os.sep):
        return None
    raiz = raiz_do_metodo(caminho)
    if raiz is None:
        return None
    if PASTAS_LIVRES & set(os.path.relpath(caminho, raiz).split(os.sep)[:-1]):
        return None
    return (f"A sessão principal não edita código ({os.path.relpath(caminho, raiz)}). Delegue a um subagente "
            "(editor para mudança já definida; Sonnet com TDD para implementar) com brief em JSON minificado.")


def main():
    try:
        motivo = decidir(json.loads(sys.stdin.read() or "{}"))
    except Exception:
        return 0
    if motivo:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": motivo}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
