#!/usr/bin/env python3
"""Hook PreToolUse (Read): nega ler inteiro um arquivo de código grande e manda usar busca por símbolo.

Arquivo de código >= 32 KB lido sem offset/limit custa caro e quase nunca é preciso inteiro: a Serena
(find_symbol, get_symbols_overview), o ccc ou um Read com offset/limit trazem só o trecho. Markdown, yaml, toml,
json e afins passam (documento se lê inteiro). Qualquer erro: deixa passar (nunca trava o trabalho).
Desligar numa sessão: OPTIMUS_LER_TUDO=1. O limiar de 32 KB veio da medição do claude-mem (abaixo disso o gate
piorava o custo)."""
import json
import os
import sys

LIMIAR = 32 * 1024
CODIGO = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".kts", ".c", ".h",
          ".cc", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".scala", ".sh", ".bash", ".zsh", ".ps1", ".lua",
          ".dart", ".vue", ".svelte", ".sql", ".ex", ".exs", ".clj", ".r", ".m", ".pl"}


def decidir(entrada):
    """Devolve o motivo da negação, ou None para deixar passar."""
    if os.environ.get("OPTIMUS_LER_TUDO") == "1" or entrada.get("tool_name") != "Read":
        return None
    ti = entrada.get("tool_input") or {}
    caminho = ti.get("file_path")
    if not isinstance(caminho, str) or ti.get("offset") is not None or ti.get("limit") is not None:
        return None
    if os.path.splitext(caminho)[1].lower() not in CODIGO:
        return None
    try:
        tamanho = os.path.getsize(caminho)
    except OSError:
        return None
    if tamanho < LIMIAR:
        return None
    return (f"{os.path.basename(caminho)} tem {tamanho // 1024} KB: não leia inteiro. Localize o trecho com a Serena "
            "(get_symbols_overview, find_symbol), ccc search ou rtk grep, e leia só ele com Read offset/limit.")


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
