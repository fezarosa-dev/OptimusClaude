"""Tempo aproximado por tarefa: só aritmética sobre medidas já feitas (ver fontes.medidas_de_tempo)."""
import re


def fmt(seg):
    m = max(1, round(seg / 60))
    if m < 60:
        return f"~{max(5, round(m / 5) * 5) if m >= 8 else m} min"
    m = round(m / 10) * 10
    h, r = divmod(m, 60)
    return f"~{h} h" + (f" {r} min" if r else "")


def media(v):
    return sum(v) / len(v) if v else None


def parse_registro(texto):
    """Duração em segundos de um registro de bateria VERDE; None para as demais."""
    if not re.search(r"\*\*Resultado:\*\* VERDE", texto):
        return None
    m = re.search(r"\*\*Duração:\*\* (\d+) s", texto)
    return int(m[1]) if m else None


def _r(seg, base, agora, texto=None):
    return {"segundos": seg, "texto": texto or fmt(seg), "base": base, "conclusao_em": agora + round(seg)}


def estimar(t, c, agora):
    """c: passo_s/n_passos, bat_s/n_bat, tarefa_s/n_tarefas, frentes, fila (worktrees), bateria_desde (ou None),
    rodando (há bateria rodando), concluidas_s {id: s}. Devolve None quando não há medida para estimar."""
    est, w = t["estado"], t.get("worktree")
    if est == "concluida":
        s = c["concluidas_s"].get(t["id"])
        return s and {"segundos": s, "texto": "levou " + fmt(s), "conclusao_em": None,
                      "base": f"medido: do primeiro commit da branch ao merge na dev ({fmt(s)})"}
    if est == "bloqueada":
        return None
    bat, passo = c.get("bat_s"), c.get("passo_s")
    wfr = t.get("wf_frac") and any(x["rodando"] for x in t["workflows"])
    if wfr:
        if not passo:
            return None
        falta = max(1, t["wf_frac"][1] - t["wf_frac"][0])
        return _r(falta * passo, f"workflow rodando: {falta} passo(s) restantes × {fmt(passo)} por passo "
                  f"(fazer, revisar ou corrigir; média de {c['n_passos']} passos de workflows terminados)", agora)
    if t.get("bateria_rodando"):
        if not (bat and c.get("bateria_desde")):
            return None
        passou = agora - c["bateria_desde"]
        return _r(max(60, bat - passou), f"bateria rodando: média de {fmt(bat)} ({c['n_bat']} baterias verdes) "
                  f"menos {fmt(passou)} que já passaram (mínimo 1 min)", agora)
    if w and w.get("a_frente") and not w.get("na_dev"):
        if not bat:
            return None
        fila = c["fila"]
        pos = fila.index(w["nome"]) if w["nome"] in fila else len(fila)
        resto = max(60, bat - (agora - c["bateria_desde"])) if c.get("rodando") and c.get("bateria_desde") else 0
        seg = (pos + 1) * bat + resto
        return _r(seg, f"branch pronta: {pos} bateria(s) na frente + a dela, × média de {fmt(bat)} "
                  f"({c['n_bat']} verdes)" + (f", mais {fmt(resto)} do que falta na bateria rodando" if resto else ""), agora)
    if not c.get("tarefa_s"):
        return None
    seg = c["tarefa_s"] / max(1, c["frentes"])
    return _r(seg, f"na fila: média de {fmt(c['tarefa_s'])} do primeiro commit ao merge ({c['n_tarefas']} tarefas "
              f"da sessão) ÷ {c['frentes']} frente(s) em paralelo", agora)
