#!/usr/bin/env python3
"""Hook PreToolUse (Bash) que o scripts/noite.py liga só para a noite (via --settings): nada sai da máquina e a
main não é tocada. Nega git push, gh pr merge/create, merge ou rebase com a main, checkout/switch para a main,
reset --hard e apagar branch remota. Qualquer erro de leitura: nega (a noite roda sem supervisão)."""
import json
import re
import sys

PROIBIDOS = [
    (r"\bgit\b[^|;&]*\bpush\b", "git push: a noite não publica nada; o push da dev é seu, de manhã"),
    (r"\bgh\s+pr\s+(merge|create|ready)\b", "PR é decisão sua, não da noite"),
    (r"\bgh\s+(release|workflow\s+run|api)\b", "a noite não mexe no GitHub"),
    (r"\bgit\b[^|;&]*\b(checkout|switch)\b[^|;&]*\b(main|master)\b", "a main não é tocada à noite"),
    (r"\bgit\b[^|;&]*\b(merge|rebase|cherry-pick)\b[^|;&]*\b(origin/)?(main|master)\b", "a main não é tocada à noite"),
    (r"\bgit\b[^|;&]*\breset\b[^|;&]*--hard\b", "reset --hard apaga trabalho; à noite, não"),
    (r"\bgit\b[^|;&]*\bbranch\b[^|;&]*\s-D\b", "apagar branch à força: à noite, não"),
]


def decidir(entrada):
    if entrada.get("tool_name") != "Bash":
        return None
    cmd = str((entrada.get("tool_input") or {}).get("command") or "")
    for padrao, motivo in PROIBIDOS:
        if re.search(padrao, cmd):
            return f"Modo noturno: {motivo}. Registre no duvidas.md o que precisava e siga com o resto."
    return None


def main():
    try:
        motivo = decidir(json.loads(sys.stdin.read() or "{}"))
    except Exception:
        motivo = "Modo noturno: não consegui ler o comando; negado por segurança."
    if motivo:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": motivo}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
