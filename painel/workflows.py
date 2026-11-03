"""Quadro dos workflows da sessão (Visão geral): nome, etapas, onde cada tarefa está, agentes vivos, tempo e tokens.

Rodando: journal.jsonl do run + o `export const meta` do script (lido sem eval) + o lançamento (args, início) achado no .jsonl da sessão.
Terminados: o <runId>.json que o Claude Code grava no fim. Todo texto que sai passa por mascarar(): o painel abre no celular."""
import glob
import json
import os
import re

import analisadores as a
import shells

RECENTES = 3
_TERM = {}  # (caminho, mtime) -> info do .json terminado: arquivo terminado não muda


def _fecha_aspas(t, i):
    """Índice logo depois da string que abre em t[i] (até o fim se não fechar)."""
    q = t[i]
    i += 1
    while i < len(t):
        if t[i] == "\\":
            i += 2
        elif t[i] == q:
            return i + 1
        else:
            i += 1
    return len(t)


def _pula(t, i):
    """Se em t[i] começa string ou comentário, o índice depois dele; senão i."""
    if t[i] in "'\"`":
        return _fecha_aspas(t, i)
    if t.startswith("//", i):
        f = t.find("\n", i)
        return len(t) if f < 0 else f
    if t.startswith("/*", i):
        f = t.find("*/", i + 2)
        return len(t) if f < 0 else f + 2
    return i


def _sem_comentarios(t):
    saida, i = [], 0
    while i < len(t):
        j = _pula(t, i)
        if j != i:
            if t[i] in "'\"`":
                saida.append(t[i:j])
            i = j
        else:
            saida.append(t[i])
            i += 1
    return "".join(saida)


def _bloco(t, i):
    """Texto entre a chave/colchete que abre em t[i] e a que fecha; None se não fechar."""
    prof, j = 0, i
    while j < len(t):
        k = _pula(t, j)
        if k != j:
            j = k
            continue
        if t[j] in "{[(":
            prof += 1
        elif t[j] in "}])":
            prof -= 1
            if prof == 0:
                return t[i + 1:j]
        j += 1
    return None


def _dividir(t):
    """Separa por vírgula no nível de cima (respeita strings, chaves e colchetes)."""
    partes, ini, prof, i = [], 0, 0, 0
    while i < len(t):
        j = _pula(t, i)
        if j != i:
            i = j
            continue
        if t[i] in "{[(":
            prof += 1
        elif t[i] in "}])":
            prof -= 1
        elif t[i] == "," and prof == 0:
            partes.append(t[ini:i])
            ini = i + 1
        i += 1
    partes.append(t[ini:])
    return [p.strip() for p in partes if p.strip()]


def _literal(v):
    """O conteúdo da primeira string de v (shortcut: não junta 'a' + 'b'); None se v não começa com string."""
    v = v.strip()
    if not v or v[0] not in "'\"`":
        return None
    corpo = v[1:_fecha_aspas(v, 0) - 1]
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m[1], m[1]), corpo)


def _pares(texto):
    d = {}
    for p in _dividir(_sem_comentarios(texto)):
        k, dois, v = p.partition(":")
        if dois:
            d[k.strip().strip("'\"`")] = v.strip()
    return d


def parse_meta(script):
    """{name, description, phases:[{title, detail}]} do `export const meta = {...}`; vazio se não houver ou não fechar."""
    vazio = {"name": None, "description": "", "phases": []}
    m = re.search(r"export\s+const\s+meta\s*=\s*\{", script) if isinstance(script, str) else None
    corpo = _bloco(script, m.end() - 1) if m else None
    if corpo is None:
        return vazio
    d = _pares(corpo)
    nome, desc = _literal(d.get("name", "")), _literal(d.get("description", ""))
    fases = []
    v = d.get("phases", "")
    inner = _bloco(v, 0) if v.startswith("[") else None
    for el in _dividir(_sem_comentarios(inner or "")):
        if el.startswith("{"):
            ps = _pares(_bloco(el, 0) or "")
            t, det = _literal(ps.get("title", "")), _literal(ps.get("detail", ""))
        else:
            t, det = _literal(el), ""
        if t:
            fases.append({"title": shells.mascarar(t)[:60], "detail": shells.mascarar(det or "")[:200]})
    return {"name": shells.mascarar(nome)[:80] if nome else None, "description": shells.mascarar(desc or "")[:300], "phases": fases}


def partes_do_rotulo(rotulo, fase):
    """'T148 revisar 2' -> ('T148', 2): tira a rodada (número no fim) e a etapa (a palavra da fase) do rótulo."""
    t = str(rotulo or "").split()
    rodada = int(t.pop()) if len(t) > 1 and t[-1].isdigit() else None
    if len(t) > 1 and fase and t[-1].casefold() == fase.casefold():
        t.pop()
    return " ".join(t), rodada


def _nomes_passos(t):
    return [str(p.get("nome") if isinstance(p, dict) else p) for p in t.get("passos") or [] if (p.get("nome") if isinstance(p, dict) else p)]


def andamento(entradas, fases, tarefas_args, vivos):
    """Etapas (feita/atual/parada/falta) e tarefas (onde cada uma está) a partir das entradas da journal.
    `vivos`: ids dos agentes com sinal recente (None = todo agente sem resultado conta como rodando)."""
    rodando = lambda e: e["status"] == "rodando" and (vivos is None or e["agentId"] in vivos)
    ordem = list(fases)
    for e in entradas:
        if e["fase"] and e["fase"] not in ordem:
            ordem.append(e["fase"])
    out, atual = [], None
    for titulo in ordem:
        es = [e for e in entradas if e["fase"] == titulo]
        ter = sum(e["status"] == "terminado" for e in es)
        vivo = any(rodando(e) for e in es)
        estado = "atual" if vivo else "falta" if not es else "feita" if ter == len(es) else "parada"
        atual = atual or (titulo if vivo else None)
        out.append({"titulo": titulo, "iniciados": len(es), "terminados": ter, "estado": estado})
    chaves, tarefas = {}, {}

    def nova(i, t=None):
        t = t or {}
        tarefas[i] = {"id": i, "passos": max(1, len(_nomes_passos(t))), "modelo": str(t.get("modelo") or ""), "effort": str(t.get("effort") or ""),
                      "agentes": 0, "feitos": 0, "etapa": "", "rodada": None, "estado": "aguardando", "ultimo": "", "_viva": ""}
    for t in tarefas_args or []:
        i = str(t.get("id"))
        nova(i, t)
        for n in [i, *_nomes_passos(t)]:
            chaves[n.casefold()] = i
    for e in entradas:
        chave, rodada = partes_do_rotulo(e["label"], e["fase"])
        i = chaves.get(chave.casefold(), chave)
        if i not in tarefas:
            nova(i)
        t = tarefas[i]
        t["agentes"] += 1
        t["feitos"] += e["status"] == "terminado"
        t["etapa"] = e["fase"] or t["etapa"]
        if rodada is not None:
            t["rodada"] = max(rodada, t["rodada"] or 0)
        if e["resumo"]:
            t["ultimo"] = e["resumo"]
        if rodando(e):
            t["_viva"] = e["fase"] or t["etapa"] or "?"
    for t in tarefas.values():
        viva = t.pop("_viva")
        t["etapa"] = viva or t["etapa"]
        t["estado"] = "rodando" if viva else "aguardando" if not t["agentes"] else "entre passos"
    return {"fases": out, "fase_atual": atual, "tarefas": list(tarefas.values())}


def _tarefas_do_args(args):
    """Só o que o painel mostra de args.tarefas: id, nomes dos passos, modelo, effort. O brief nunca é guardado."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return []
    lista = args.get("tarefas") if isinstance(args, dict) else None
    saida = []
    for t in lista[:60] if isinstance(lista, list) else []:
        if isinstance(t, dict) and t.get("id") is not None:
            saida.append({"id": shells.mascarar(t["id"])[:60], "passos": [shells.mascarar(n)[:60] for n in _nomes_passos(t)],
                          "modelo": str(t.get("modelo") or "")[:20], "effort": str(t.get("effort") or "")[:20]})
    return saida


def _lancamento(est, linha):
    if (b"Workflow" not in linha and b"Run ID: wf_" not in linha) or linha.startswith(b'{"type":"api-request'):
        return
    try:
        e = json.loads(linha)
        ts = a.iso_ts(e["timestamp"]) if e.get("timestamp") else 0
        c = (e.get("message") or {}).get("content")
        for b in c if isinstance(c, list) else []:
            if not isinstance(b, dict):
                continue
            inp = b.get("input") or {}
            if b.get("type") == "tool_use" and b.get("name") == "Workflow":
                est["usos"][b["id"]] = {"script_path": str(inp.get("scriptPath") or "")[:500] or None,
                                        "meta": parse_meta(inp["script"]) if isinstance(inp.get("script"), str) else None,
                                        "tarefas": _tarefas_do_args(inp.get("args"))}
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in est["usos"]:
                m = re.search(r"Run ID: (wf_[\w-]+)", " ".join(shells._textos({"content": b.get("content")})))
                if m:
                    est["runs"][m[1]] = {**est["usos"].pop(b["tool_use_id"]), "inicio": ts}
    except (ValueError, KeyError, TypeError, AttributeError):
        pass


def planejados(lanc):
    """runId -> total de passos planejado no args.tarefas (tarefa sem passos conta 1); run sem tarefas fica de fora."""
    return {wid: sum(max(1, len(t.get("passos") or [])) for t in r["tarefas"])
            for wid, r in ((lanc or {}).get("runs") or {}).items() if r.get("tarefas")}


def ler_lancamentos(est, caminho):
    """Lê só o que cresceu do .jsonl da sessão: cada Workflow lançado (runId -> meta/script, tarefas do args, início)."""
    return shells.ler_incremental(est, caminho, lambda: {"usos": {}, "runs": {}}, _lancamento)


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def terminado(wid, info, fim):
    """O bloco de um workflow que acabou, a partir do <runId>.json."""
    info = info if isinstance(info, dict) else {}
    ini, dur = _num(info.get("startTime")), _num(info.get("durationMs"))
    fases = [shells.mascarar(p.get("title"))[:60] for p in info.get("phases") or [] if isinstance(p, dict) and p.get("title")]
    return {"id": wid, "nome": shells.mascarar(info.get("workflowName") or wid)[:80], "status": str(info.get("status") or "?")[:20],
            "resumo": shells.mascarar(info.get("summary"))[:200], "inicio": ini / 1000 if ini else None, "fim": fim,
            "duracao": dur / 1000 if dur is not None else None, "agentes": int(_num(info.get("agentCount")) or 0),
            "tokens": int(_num(info.get("totalTokens")) or 0), "fases": fases}


def _ler(caminho, maximo=200_000):
    try:
        with open(caminho, "rb") as f:
            return f.read(maximo).decode("utf-8", "replace")
    except (OSError, TypeError):
        return None


PARADO_SEGUNDOS = 2 * 3600  # sem sinal há mais que isso e sem o .json final: o workflow morreu (sessão encerrada)
RAIZES_CLAUDE = tuple(r for r in (os.environ.get("CLAUDE_CONFIG_DIR"), "~/.claude") if r)


def _permitido(caminho, projeto):
    """scriptPath vem do .jsonl: só abre se o realpath estiver em ~/.claude ou no projeto."""
    if not caminho:
        return False
    real = os.path.realpath(caminho)
    raizes = [os.path.realpath(os.path.expanduser(r)) for r in (*RAIZES_CLAUDE, projeto) if r]
    return any(real == r or real.startswith(r + os.sep) for r in raizes)


def _meta(sd, wid, run, projeto=None):
    """Meta do run: a cópia do script que o Claude Code guarda por run, depois o script inline, depois o scriptPath."""
    for ps in glob.glob(f"{glob.escape(sd)}/workflows/scripts/*{glob.escape(wid)}.js")[:1]:
        m = parse_meta(_ler(ps))
        if m["name"]:
            return m
    m = run.get("meta")
    if m and m.get("name"):
        return m
    sp = run.get("script_path")
    m = parse_meta(_ler(sp) if _permitido(sp, projeto) else None)
    return m if m["name"] else {"name": None, "description": "", "phases": m["phases"]}


def _mascarar_tudo(x):
    if isinstance(x, str):
        return shells.mascarar(x)
    if isinstance(x, list):
        return [_mascarar_tudo(i) for i in x]
    if isinstance(x, dict):
        return {k: _mascarar_tudo(v) for k, v in x.items()}
    return x


def _recentes(sd, fora, parados=()):
    achados = []
    for p in glob.glob(f"{glob.escape(sd)}/workflows/wf_*.json"):
        wid = os.path.basename(p)[:-5]
        if wid not in fora:
            try:
                achados.append((os.path.getmtime(p), wid, p))
            except OSError:
                pass
    saida = []
    for mt, wid, p in sorted(achados, reverse=True)[:RECENTES]:
        if (p, mt) not in _TERM:
            try:
                _TERM[(p, mt)] = json.loads(_ler(p, 4 << 20) or "{}")
            except ValueError:
                _TERM[(p, mt)] = {}
        saida.append(terminado(wid, _TERM[(p, mt)], mt))
    return sorted([*saida, *parados], key=lambda x: x["fim"] or 0, reverse=True)[:RECENTES]


def coletar(sd, wfs, ags, lanc, con, agora, ativo=120, projeto=None):
    """{rodando: [quadro por workflow vivo], recentes: [últimos 3 terminados, mais os parados]}.
    Rodando = lançado na sessão e sem <runId>.json (só escrito no fim); sem sinal há `ativo` s o cartão fica com o aviso."""
    runs = (lanc or {}).get("runs", {})
    rodando, parados = [], []
    for wf in wfs:
        wid = wf["id"]
        if wid not in runs or os.path.exists(f"{sd}/workflows/{wid}.json"):
            continue
        sinal = max([x.get("ultimo_sinal") or 0 for x in ags if x.get("workflow") == wid] + [wf.get("atividade") or 0]) or None
        if sinal and agora - sinal > PARADO_SEGUNDOS:
            parados.append(terminado(wid, {"workflowName": wf.get("nome"), "status": "killed", "agentCount": wf.get("agentes"),
                                           "startTime": (runs[wid].get("inicio") or 0) * 1000 or None}, sinal))
            continue
        wid = wf["id"]
        ents = a.parse_journal(_ler(f"{sd}/subagents/workflows/{wid}/journal.jsonl", 4 << 20) or "")
        run = runs.get(wid, {})
        meta = _meta(sd, wid, run, projeto)
        vivos = [x for x in ags if x.get("workflow") == wid and x.get("ativo")]
        r = andamento(ents, [p["title"] for p in meta["phases"]], run.get("tarefas"), {x["id"] for x in vivos})
        det = {p["title"]: p["detail"] for p in meta["phases"]}
        for f in r["fases"]:
            f["detalhe"] = det.get(f["titulo"], "")
        desde = run.get("inicio") or min((x["inicio"] for x in ags if x.get("workflow") == wid and x.get("inicio")), default=None)
        c = next((x for x in (con or {}).get("workflows", []) if x["id"] == wid), None)
        rodando.append({"id": wid, "nome": meta["name"] or wid, "descricao": meta["description"], "desde": desde,
                        "segundos": agora - desde if desde else None,
                        "sem_sinal": agora - sinal if sinal and agora - sinal > ativo else None, "tokens": c["tokens"] if c else None, **r,
                        "agentes_total": len(ents), "agentes_feitos": sum(e["status"] == "terminado" for e in ents),
                        "agentes": [{"rotulo": x["rotulo"][:120], "modelo": x.get("modelo", ""), "effort": x.get("effort", ""),
                                     "fase": x.get("fase", ""), "inicio": x.get("inicio")} for x in vivos]})
    return _mascarar_tudo({"rodando": rodando, "recentes": _recentes(sd, {q["id"] for q in rodando}, parados)})
