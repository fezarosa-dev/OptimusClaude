#!/usr/bin/env python3
"""Statusline do Claude Code: lê o JSON do stdin, guarda o retrato da sessão para o painel e imprime uma linha.
Só biblioteca padrão, sem rede. Qualquer erro: imprime o que deu e sai 0 (nunca derruba a barra)."""
import json
import os
import re
import sys
import time

DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
ROTACAO_BYTES = 2_000_000
GUARDAR_SEGUNDOS = 8 * 86400


def pasta():
    return os.path.expanduser(os.environ.get("CLAUDE_LIMITES_DIR") or "~/.cache/claude-limites")


def _d(x):
    return x if isinstance(x, dict) else {}


def _n(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) != float("inf") else None


def _escrever(caminho, texto):
    tmp = f"{caminho}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(texto)
        os.replace(tmp, caminho)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _janela(rl, nome):
    j = _d(_d(rl).get(nome))
    return _n(j.get("used_percentage")), _n(j.get("resets_at"))


def _ultima_linha(caminho):
    try:
        with open(caminho, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 4096))
            ls = f.read().decode("utf-8", "replace").splitlines()
        return json.loads(ls[-1]) if ls else None
    except (OSError, ValueError):
        return None


def _rotacionar(caminho, agora):
    corte = agora - GUARDAR_SEGUNDOS
    mantidas = []
    with open(caminho, encoding="utf-8", errors="replace") as f:
        for l in f:
            try:
                if _n(json.loads(l).get("t")) >= corte:
                    mantidas.append(l if l.endswith("\n") else l + "\n")
            except (ValueError, TypeError, AttributeError):
                pass
    _escrever(caminho, "".join(mantidas))


def _historico(dir_, h5, h5r, sem, semr, agora):
    if h5 is None and sem is None:
        return
    novo = {"t": int(agora), "h5": h5, "h5_reset": h5r, "sem": sem, "sem_reset": semr}
    caminho = os.path.join(dir_, "historico.jsonl")
    ult = _ultima_linha(caminho)
    chaves = ("h5", "h5_reset", "sem", "sem_reset")
    if isinstance(ult, dict) and all(ult.get(k) == novo[k] for k in chaves):
        return
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(json.dumps(novo) + "\n")
    if os.path.getsize(caminho) > ROTACAO_BYTES:
        _rotacionar(caminho, agora)


def _hora(epoch, com_dia):
    t = time.localtime(epoch)
    return (DIAS[t.tm_wday] + " " if com_dia else "") + time.strftime("%H:%M", t)


def linha(d, agora=None):
    rl = _d(d.get("rate_limits"))
    partes = []
    for nome, rotulo, dia in (("five_hour", "5h", False), ("seven_day", "semana", True)):
        pct, rst = _janela(rl, nome)
        if pct is not None:
            p = f"{rotulo} {pct:.0f}%"
            if rst is not None:
                try:
                    p += f" (volta {_hora(rst, dia)})"
                except (OverflowError, OSError, ValueError):
                    pass
            partes.append(p)
    ctx = _n(_d(d.get("context_window")).get("used_percentage"))
    if ctx is not None:
        partes.append(f"contexto {ctx:.0f}%")
    custo = _n(_d(d.get("cost")).get("total_cost_usd"))
    if custo is not None:
        partes.append(f"US$ {custo:.2f}".replace(".", ","))
    return " · ".join(partes) or "sem dados de limite"


def processar(d, dir_, agora=None):
    """Grava o retrato e o histórico; devolve a linha. Falha de gravação não impede a linha."""
    agora = time.time() if agora is None else agora
    d = _d(d)
    try:
        os.makedirs(os.path.join(dir_, "sessoes"), mode=0o700, exist_ok=True)
        os.chmod(dir_, 0o700)
        sid = re.sub(r"[^A-Za-z0-9_-]", "_", str(d.get("session_id") or "sem-id"))[:80]
        m, c = _d(d.get("model")), d.get("cwd")
        retrato = {"gravado_em": int(agora), "session_id": sid, "cwd": c if isinstance(c, str) else None,
                   "modelo": {"id": m.get("id"), "display_name": m.get("display_name")} if m else None,
                   "versao": d.get("version"), "rate_limits": d.get("rate_limits"), "cost": d.get("cost"),
                   "context_window": d.get("context_window"), "exceeds_200k_tokens": d.get("exceeds_200k_tokens")}
        _escrever(os.path.join(dir_, "sessoes", sid + ".json"), json.dumps(retrato))
        rl = d.get("rate_limits")
        h5, h5r = _janela(rl, "five_hour")
        sem, semr = _janela(rl, "seven_day")
        _historico(dir_, h5, h5r, sem, semr, agora)
    except Exception:  # a statusline nunca cai por causa do painel
        pass
    return linha(d, agora)


def main():
    try:
        d = json.loads(sys.stdin.read() or "null")
    except (ValueError, OSError):
        d = None
    try:
        print(processar(d, pasta()) if isinstance(d, dict) else "sem dados de limite")
    except Exception:
        print("sem dados de limite")
    return 0


if __name__ == "__main__":
    sys.exit(main())
