#!/usr/bin/env python3
"""Hook PostToolUse: quando o contexto da sessão principal passa de 70% (e de novo em 85%), avisa o próprio Claude
para fechar o passo atual e rodar a skill session-handoff.

Lê a porcentagem do retrato que a statusline do painel grava (~/.cache/claude-limites/sessoes/<sessão>.json, ou
CLAUDE_LIMITES_DIR). Sem statusline do painel, não faz nada. Avisa uma vez por limiar por sessão (marca em
avisos/). Retrato com mais de 10 min é ignorado. Subagente não recebe aviso. Qualquer erro: silêncio, saída 0."""
import json
import os
import re
import sys
import time

LIMIARES = (85, 70)
VELHO_SEGUNDOS = 600


def pasta():
    return os.path.expanduser(os.environ.get("CLAUDE_LIMITES_DIR") or "~/.cache/claude-limites")


def aviso(entrada, dir_, agora=None):
    """Devolve o texto do aviso (e grava a marca), ou None."""
    agora = time.time() if agora is None else agora
    if entrada.get("agent_id") or entrada.get("agent_type"):
        return None
    sid = re.sub(r"[^A-Za-z0-9_-]", "_", str(entrada.get("session_id") or ""))[:80]
    if not sid:
        return None
    with open(os.path.join(dir_, "sessoes", sid + ".json"), encoding="utf-8") as f:
        retrato = json.load(f)
    if agora - (retrato.get("gravado_em") or 0) > VELHO_SEGUNDOS:
        return None
    usado = (retrato.get("context_window") or {}).get("used_percentage")
    if not isinstance(usado, (int, float)):
        return None
    for limiar in LIMIARES:
        if usado >= limiar:
            marca = os.path.join(dir_, "avisos", f"{sid}-{limiar}")
            if os.path.exists(marca):
                return None
            os.makedirs(os.path.dirname(marca), mode=0o700, exist_ok=True)
            open(marca, "w").close()
            return (f"Contexto em {usado:.0f}%. Termine o passo atual sem abrir frente nova, rode a skill "
                    "session-handoff e diga ao usuário que é hora de abrir uma sessão nova com o handoff.")
    return None


def main():
    try:
        texto = aviso(json.loads(sys.stdin.read() or "{}"), pasta())
    except Exception:
        return 0
    if texto:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": texto}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
