"""Coleta o estado lendo o disco, o git (só leitura), ps e docker. Cada fonte é isolada em servidor.py."""
import glob
import json
import os
import re
import subprocess
import threading
import time

import analisadores as a
import tempo
from workflows import PARADO_SEGUNDOS


def _ler(caminho, maximo=None):
    with open(caminho, "rb") as f:
        if maximo:
            f.seek(0, 2)
            tam = f.tell()
            f.seek(max(0, tam - maximo))
        return f.read().decode("utf-8", "replace")


def _cmd(args, cwd=None, timeout=8):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.stdout


def _mtime(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return 0


def _json(p, padrao=None):
    try:
        return json.loads(_ler(p))
    except (OSError, ValueError):
        return padrao


def sessao_dir(cfg):
    base = cfg["sessoes"]
    if cfg.get("sessao"):
        return os.path.join(base, cfg["sessao"])
    cand = [d for d in glob.glob(base + "/*/") if os.path.isdir(d + "subagents")]
    return max(cand, key=_mtime).rstrip("/") if cand else None


def _ramo(cfg):
    return cfg.get("ramo") or "dev"  # ramo de integração (onde as branches entram antes da principal)


def _no_projeto(cfg, chave, padrao):
    """Arquivo do projeto pelo config (relativo ao projeto); o quadro sem o arquivo fica vazio."""
    return os.path.join(cfg["projeto"], cfg.get(chave) or padrao)


def _ler_ou_vazio(caminho):
    try:
        return _ler(caminho)
    except FileNotFoundError:
        return ""


def git_worktrees(cfg):
    proj, ramo = cfg["projeto"], _ramo(cfg)
    # segundos pais dos merges na dev: o ramo cujo topo está aqui já entrou
    merged = set()
    for l in _cmd(["git", "log", ramo, "--merges", "-400", "--format=%P"], proj).splitlines():
        p = l.split()
        if len(p) > 1:
            merged.add(p[1])
    saida, atual = [], {}
    for l in _cmd(["git", "worktree", "list", "--porcelain"], proj).splitlines() + [""]:
        if not l:
            if atual.get("worktree", "").startswith(cfg["worktrees"]):
                saida.append(atual)
            atual = {}
        else:
            k, _, v = l.partition(" ")
            atual[k] = v
    res = []
    for w in saida:
        if not w.get("HEAD"):  # bare/sem commit: nada a medir
            continue
        ramo = w.get("branch", "").replace("refs/heads/", "")
        pasta = w["worktree"]
        n = _cmd(["git", "rev-list", "--count", f"{ramo}..{w['HEAD']}"], proj).strip()
        sujo = len(_cmd(["git", "--no-optional-locks", "status", "--porcelain"], pasta, 6).splitlines())
        nome = os.path.basename(pasta)
        res.append({
            "nome": nome, "ramo": ramo, "pasta": pasta,
            "tarefa": a.numero_da_tarefa(ramo) or a.numero_da_tarefa(nome),
            "a_frente": int(n) if n.isdigit() else None,
            "na_dev": w["HEAD"] in merged,
            "mudancas_nao_commitadas": sujo,
        })
    return res


def git_merges(cfg):
    out = _cmd(["git", "log", _ramo(cfg), "--merges", "-12", "--format=%h|%ct|%s"], cfg["projeto"])
    r = []
    for l in out.splitlines():
        h, t, s = l.split("|", 2)
        if s.startswith(f"chore(merge): {_ramo(cfg)} na branch"):  # o ramo de integração trazido para a branch não é entrega
            continue
        r.append({"sha": h, "quando": int(t), "mensagem": s})
    return r


def _ultima_fala(caminho):
    for linha in reversed(_ler(caminho, 96_000).splitlines()):
        try:
            e = json.loads(linha)
        except ValueError:
            continue
        if e.get("type") != "assistant":
            continue
        c = (e.get("message") or {}).get("content")
        if isinstance(c, list):
            for it in reversed(c):
                if it.get("type") == "text" and it.get("text", "").strip():
                    return " ".join(it["text"].split())[:220]
                if it.get("type") == "tool_use":
                    return "usando " + str(it.get("name"))
    return ""


def _inicio(caminho):
    try:
        with open(caminho, "rb") as f:
            e = json.loads(f.readline())
        from datetime import datetime
        return datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


EFFORT_PEDACO = 64 << 10   # bytes por leitura
EFFORT_LIMITE = 1 << 20    # o 1º pedido do agente vem logo no começo do histórico; além disso, desiste (arquivos têm vários MB)
EFFORT_ORDEM = ("low", "medium", "high", "xhigh", "max")
_EFFORT_RX = re.compile(rb'"output_config"\s*:\s*\{\s*"effort"\s*:\s*"(\w+)"')
_EFFORT = {}  # caminho -> (tamanho, effort, limite_esgotado): effort achado vale para sempre; vazio só é refeito se o arquivo cresceu


def effort_do_historico(caminho, cache=None):
    """Effort do agente: primeira ocorrência de "output_config":{"effort":...} no começo do .jsonl ("" se não achar)."""
    cache = _EFFORT if cache is None else cache
    c = cache.get(caminho)
    if c and (c[1] or c[2]):  # achado, ou limite já lido sem achar: não relê
        return c[1]
    try:
        tam = os.path.getsize(caminho)
        if c and c[0] == tam:
            return ""
        achado, resto, lido = "", b"", 0
        with open(caminho, "rb") as f:
            while lido < EFFORT_LIMITE:
                bloco = f.read(EFFORT_PEDACO)
                if not bloco:
                    break
                lido += len(bloco)
                m = _EFFORT_RX.search(resto + bloco)
                if m:
                    achado = m[1].decode()
                    break
                resto = bloco[-80:]  # o marcador pode ter sido cortado entre dois pedaços
    except OSError:
        return ""
    cache[caminho] = (tam, achado, not achado and lido >= EFFORT_LIMITE)
    return achado


def efforts_ordenados(valores):
    vs = {v for v in valores if v}
    return sorted(vs, key=lambda v: (EFFORT_ORDEM.index(v) if v in EFFORT_ORDEM else len(EFFORT_ORDEM), v))


def agentes_e_workflows(cfg, sd):
    agora, ativo = time.time(), cfg["ativo_segundos"]
    metas, wfs = {}, []
    for m in glob.glob(sd + "/subagents/agent-*.meta.json") + glob.glob(sd + "/subagents/workflows/*/agent-*.meta.json"):
        aid = os.path.basename(m)[len("agent-"):-len(".meta.json")]
        metas[aid] = {"meta": _json(m, {}), "jsonl": m[:-len(".meta.json")] + ".jsonl"}
    jour = {}
    for jp in sorted(glob.glob(sd + "/subagents/workflows/wf_*/journal.jsonl"), key=_mtime, reverse=True)[:12]:
        wid = os.path.basename(os.path.dirname(jp))
        ents = a.parse_journal(_ler(jp))
        for e in ents:
            jour[e["agentId"]] = {**e, "wf": wid}
        info = _json(f"{sd}/workflows/{wid}.json", {})
        feitos = sum(e["status"] == "terminado" for e in ents)
        texto = " ".join([info.get("workflowName", ""), info.get("summary", "")] + [e["label"] for e in ents])
        tarefas = sorted({int(n) for n in re.findall(r"\bT(\d+)", texto)})
        st = a.status_workflow(info.get("status"), _mtime(jp), _mtime(f"{sd}/workflows/{wid}.json"))
        rodando = st not in ("killed", "completed", "failed") and any(e["status"] == "rodando" and agora - _mtime(metas.get(e["agentId"], {}).get("jsonl", "")) < ativo for e in ents)
        # em curso: sem o .json final e com sinal recente; entre um passo e outro nenhum agente está vivo, mas o workflow segue
        sinal = max([_mtime(jp)] + [_mtime(metas[e["agentId"]]["jsonl"]) for e in ents if e["agentId"] in metas])
        em_curso = rodando or (st is None and agora - sinal < PARADO_SEGUNDOS)
        wfs.append({
            "id": wid, "nome": info.get("workflowName") or wid, "status": st or ("rodando" if rodando else "?"),
            "resumo": (info.get("summary") or "")[:200], "agentes": len(ents), "feitos": feitos, "rodando": rodando, "em_curso": em_curso,
            "tarefas": tarefas, "atividade": _mtime(jp),
            "efforts": efforts_ordenados(effort_do_historico(metas[e["agentId"]]["jsonl"]) or metas[e["agentId"]]["meta"].get("effort", "")
                                         for e in ents if e["agentId"] in metas),
            "vereditos": [e["resumo"] for e in ents if e["resumo"]][-6:],
            "fases": sorted({e["fase"] for e in ents if e["fase"]}),
        })
    ags = []
    recentes = sorted(metas.items(), key=lambda kv: _mtime(kv[1]["jsonl"]), reverse=True)[:40]
    for aid, d in recentes:
        mt, meta, j = _mtime(d["jsonl"]), d["meta"], jour.get(aid)
        fresco = agora - mt < ativo
        if j:
            ativo_ = j["status"] == "rodando" and fresco
        else:
            ativo_ = not meta.get("finished") and fresco
        ini = _inicio(d["jsonl"]) if os.path.exists(d["jsonl"]) else None
        ags.append({
            "id": aid, "rotulo": (j or {}).get("label") or meta.get("description") or aid,
            "modelo": meta.get("model", ""), "effort": meta.get("effort") or effort_do_historico(d["jsonl"]),
            "workflow": (j or {}).get("wf", ""), "fase": (j or {}).get("fase") or meta.get("workflowPhase", ""),
            "ativo": ativo_, "sem_sinal": bool(j and j["status"] == "rodando" and not fresco),
            "resumo": (j or {}).get("resumo", ""),
            "ultimo_sinal": mt, "inicio": ini,
            "fala": _ultima_fala(d["jsonl"]) if os.path.exists(d["jsonl"]) and (ativo_ or agora - mt < 900) else "",
        })
    return ags, wfs


def baterias(cfg, wts):
    agora = time.time()
    cache = os.path.expanduser(cfg["cache"])
    bateria_cmd, cadeia_cmd = cfg.get("bateria_comando") or "testar_como_o_ci.py", cfg.get("bateria_cadeia") or "encadear-baterias"
    wt_raiz = (cfg.get("worktrees") or "/nenhum").rstrip("/") + "/"
    padrao = cfg.get("bateria_logs") or "bateria-*.log"
    pre, _, suf = padrao.partition("*")
    ps = _cmd(["ps", "-eo", "pid,etimes,args"])
    rodando, fila = None, []
    for l in ps.splitlines()[1:]:
        p = l.split(None, 2)
        if len(p) < 3:
            continue
        if cadeia_cmd in p[2] and "ps -eo" not in p[2]:
            for tok in p[2].split():
                if re.match(r"^[\w.-]+:[^:\s]+:", tok):
                    fila.append(tok.split(":")[0])
        elif bateria_cmd in p[2] and not p[2].startswith(("grep", "ps ")):
            try:
                m = re.match(re.escape(wt_raiz) + r"([^/]+)", os.readlink(f"/proc/{p[0]}/cwd"))
            except OSError:
                continue
            if m and (not rodando or agora - int(p[1]) < rodando["desde"]):  # o mais antigo é o pai
                rodando = {"wt": m[1], "desde": agora - int(p[1])}
    logs = []
    caminhos = sorted(glob.glob(os.path.join(cache, padrao)), key=_mtime, reverse=True)[:10]
    try:
        durs = duracoes_baterias(caminhos)
    except (OSError, subprocess.SubprocessError, ValueError):
        durs = {}
    for lp in caminhos:
        nome = os.path.basename(lp)[len(pre):len(os.path.basename(lp)) - len(suf)]
        b = a.parse_bateria(_ler(lp))
        b.update({"wt": nome, "atividade": _mtime(lp), "duracao": durs.get(lp), "ativa": agora - _mtime(lp) < cfg["ativo_segundos"] and not b["terminou"]})
        b["falhou"] = [r["nome"] for r in b["resumo"] if r["status"] == "FALHOU"]
        b["resumo"] = [r for r in b["resumo"] if r["status"] != "OK"]
        logs.append(b)
    cadeia = {"resultados": [], "na_dev": [], "parou": None}
    outs = sorted(glob.glob(cfg["saidas"] + "/*/tasks/*.output"), key=_mtime, reverse=True)[:30]
    for o in outs:
        t = _ler(o, 200_000)
        if re.search(r"^== \S+ saida=", t, re.M):
            cadeia = a.parse_cadeia(t)
            cadeia["arquivo_atividade"] = _mtime(o)
            break
    feitos = {r["wt"] for r in cadeia["resultados"]}
    fila = [w for w in dict.fromkeys(fila) if w not in feitos and not (rodando and w == rodando["wt"])]
    if rodando:
        for b in logs:
            if b["wt"] == rodando["wt"]:
                b["ativa"] = True
        rodando["total_tela"] = cfg.get("testes_de_tela_total") or 0
    return {"rodando": rodando, "fila": fila, "logs": logs, "cadeia": cadeia}


_UNID = {"b": 1 / 1048576, "kib": 1 / 1024, "kb": 1 / 1000, "mib": 1, "mb": 1, "gib": 1024, "gb": 1000, "tib": 1048576}
_docker_cache = {"t": 0, "dados": None, "ocupado": False}


def _mb(txt):
    m = re.match(r"\s*([\d.]+)\s*([A-Za-z]+)", txt)
    return float(m.group(1)) * _UNID[m.group(2).lower()]


def parse_docker(linhas, total_mb):
    """Soma o uso dos contêineres; limite perto da RAM da máquina = sem teto."""
    mb, sem = 0.0, []
    for l in linhas:
        d = json.loads(l)
        uso, _, lim = d["MemUsage"].partition("/")
        mb += _mb(uso)
        if _mb(lim) >= total_mb * 0.95:
            sem.append(d["Name"])
    return {"mb": round(mb), "n": len(linhas), "sem_teto": sem}


def parse_fatia(txt):
    v = dict(l.split("=", 1) for l in txt.splitlines() if "=" in l)
    def n(k):
        return int(v[k]) // 1048576 if v.get(k, "").isdigit() else None
    return n("MemoryCurrent"), n("MemoryMax")


def _docker_stats():
    d = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{json .}}"],
                       capture_output=True, text=True, timeout=8)
    return d.stdout.splitlines() if d.returncode == 0 else None


def docker_em_cache(ler=_docker_stats, validade=15):
    """Devolve o último resultado já lido e, se velho, atualiza numa thread (o docker stats leva ~2 s)."""
    c = _docker_cache
    if time.time() - c["t"] > validade and not c["ocupado"]:
        c["ocupado"] = True
        def atualizar():
            try:
                c["dados"] = ler()
            except (OSError, subprocess.SubprocessError):
                c["dados"] = None
            finally:
                c["t"], c["ocupado"] = time.time(), False
        threading.Thread(target=atualizar, daemon=True).start()
    return c["dados"]


def montar_teto(cfg, cgroup_mb, fatia, conteineres, maquina):
    teto = cfg.get("teto_memoria_mb", 8192)
    fat_mb, fat_teto = fatia if fatia else (None, None)
    partes = [{"nome": "Claude e agentes (este cgroup)", "mb": cgroup_mb},
              {"nome": "Fatia de testes", "mb": fat_mb, "teto_mb": fat_teto},
              {"nome": "Contêineres", "mb": conteineres["mb"] if conteineres else None,
               "n": conteineres["n"] if conteineres else None,
               "sem_teto": conteineres["sem_teto"] if conteineres else []}]
    if not cfg.get("fatia_testes"):  # sem fatia systemd configurada: a parte não existe (não é "faltando")
        partes.pop(1)
    usado = sum(p["mb"] for p in partes if p["mb"] is not None)
    return {"teto_mb": teto, "usado_mb": usado, "livre_mb": max(teto - usado, 0), "pct": round(usado * 100 / teto),
            "partes": partes, "maquina": maquina, "faltando": [p["nome"] for p in partes if p["mb"] is None]}


def _teto(cfg, maquina):
    try:
        dist = int(_ler("/sys/fs/cgroup/memory.current")) // 1048576
    except (OSError, ValueError):
        dist = None
    fatia = None
    if cfg.get("fatia_testes"):
        try:
            fatia = parse_fatia(subprocess.run(["systemctl", "--user", "show", cfg["fatia_testes"], "-p", "MemoryCurrent", "-p", "MemoryMax"],
                                               capture_output=True, text=True, timeout=3).stdout)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        dk = docker_em_cache()
        cont = parse_docker(dk, maquina["total_mb"]) if dk is not None else None
    except (ValueError, KeyError):
        cont = None
    return montar_teto(cfg, dist, fatia, cont, maquina)


def ambiente(cfg):
    r = {}
    trava = os.path.join(os.path.expanduser(cfg["cache"]), cfg["trava_testes"]) if cfg.get("trava_testes") else None
    r["trava"] = _json(trava + "/dono.json") if trava and os.path.isdir(trava) else None
    try:
        d = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=5)
        r["conteineres"] = d.stdout.split() if d.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        r["conteineres"] = None
    mem = {}
    for l in _ler("/proc/meminfo").splitlines():
        k, _, v = l.partition(":")
        mem[k] = int(v.split()[0])
    r["memoria"] = {"total_mb": mem["MemTotal"] // 1024, "livre_mb": mem["MemAvailable"] // 1024}
    r["teto"] = _teto(cfg, r["memoria"])
    return r


def tarefas(cfg, wts, wfs, bat):
    proj = cfg["projeto"]
    todas = a.parse_tasks(_ler_ou_vazio(_no_projeto(cfg, "arquivo_tarefas", "TASKS.md")))
    rod = bat["rodando"]["wt"] if bat["rodando"] else None
    por_wt = {n: a.melhor_worktree([w for w in wts if w["tarefa"] == n], rod) for n in {w["tarefa"] for w in wts if w["tarefa"]}}
    wf_de = {}
    for w in wfs:
        for n in w["tarefas"]:
            wf_de.setdefault(n, []).append(w)
    fila = set(bat["fila"])
    saida = []
    for t in todas:
        w = por_wt.get(t["id"])
        if t["id"] < cfg["leva_a_partir_de"] and not w:
            continue
        estado = t["estado"]
        wfr = next((x for x in wf_de.get(t["id"], []) if x.get("em_curso", x["rodando"])), None)
        estado = a.estado_efetivo(estado, w, bool(wfr))
        brodando = bool(w and w["nome"] == rod)
        # total planejado (args.tarefas) quando há; só os agentes lançados faz a % cair a cada passo novo
        frac = (wfr["feitos"], wfr.get("planejados") or wfr["agentes"]) if wfr else None
        pct = a.percentual(estado, w, frac, brodando)
        saida.append({**t, "estado": estado, "wf_frac": frac, "percentual": pct, "worktree": w,
                      "workflows": [{"id": x["id"], "nome": x["nome"], "rodando": x["rodando"]} for x in wf_de.get(t["id"], [])],
                      "bateria_rodando": brodando, "na_fila_de_baterias": bool(w and w["nome"] in fila)})
    return saida


def duvidas(cfg):
    t = _ler_ou_vazio(_no_projeto(cfg, "arquivo_duvidas", "duvidas.md"))
    return {"abertas": a.parse_duvidas(t), "avisos": [x[:260] for x in a.parse_avisos(t, cfg.get("secao_avisos") or "## Avisar")]}


def publicacao(cfg):
    p = _no_projeto(cfg, "arquivo_publicacao", "docs/publicacao-pendente.md")
    return {"itens": len(re.findall(r"^- ", _ler_ou_vazio(p), re.M)), "atividade": _mtime(p)}


def respostas(pasta):
    """O que foi respondido pelo painel: pendentes (o Claude ainda não pegou) e as últimas entregues."""
    def ler(sub, n):
        r = []
        for p in sorted(glob.glob(os.path.join(pasta, sub, "*.json")), reverse=True)[:n]:
            d = _json(p, {})
            r.append({k: d.get(k) for k in ("id", "titulo", "opcao", "opcoes", "enviada_em")}
                     | {"texto": (d.get("texto") or "")[:300], "outro": (d.get("outro") or "")[:300]})
        return r
    return {"pendentes": ler("pendentes", 50), "entregues": ler("entregues", 10)}


CAMPOS = (("entrada", "input_tokens"), ("saida", "output_tokens"), ("cache_lido", "cache_read_input_tokens"),
          ("cache_criado", "cache_creation_input_tokens"))


def _zero():
    return {k: 0 for k, _ in CAMPOS}


def ler_uso(est, caminho):
    """Soma o usage das mensagens do assistente lendo só o que cresceu desde a última vez (posição guardada em est).
    A mesma mensagem sai em várias linhas (uma por bloco): conta uma vez, pelo message.id."""
    st = os.stat(caminho)
    if not est or est.get("ino") != st.st_ino or st.st_size < est["pos"]:  # arquivo novo ou trocado: recomeça
        est = {"ino": st.st_ino, "pos": 0, "ids": set(), "tot": _zero(), "modelos": {}, "ini": None, "fim": None}
    if st.st_size == est["pos"]:
        return est
    with open(caminho, "rb") as f:
        f.seek(est["pos"])
        bloco = f.read(st.st_size - est["pos"])
    corte = bloco.rfind(b"\n") + 1  # linha pela metade fica para a próxima leitura
    for linha in bloco[:corte].splitlines():
        if b'"usage"' not in linha or b'"assistant"' not in linha:
            continue
        try:
            e = json.loads(linha)
            m = e["message"]
            u = m["usage"]
        except (ValueError, KeyError, TypeError):
            continue
        if e.get("type") != "assistant" or not isinstance(u, dict):
            continue
        try:
            ts = a.iso_ts(e["timestamp"])
            est["ini"] = ts if est["ini"] is None else min(est["ini"], ts)
            est["fim"] = ts if est["fim"] is None else max(est["fim"], ts)
        except (KeyError, ValueError, AttributeError):
            pass
        mid, modelo = m.get("id"), m.get("model") or "?"
        if mid in est["ids"] or modelo == "<synthetic>":
            continue
        if mid:
            est["ids"].add(mid)
        pm = est["modelos"].setdefault(modelo, _zero())
        for k, campo in CAMPOS:
            v = u.get(campo) or 0
            est["tot"][k] += v
            pm[k] += v
    est["pos"] += corte
    return est


def _somar(dst, src):
    for k in src:
        dst[k] = dst.get(k, 0) + src[k]
    return dst


def _com_total(d):
    return {**d, "tokens": sum(d.get(k, 0) for k, _ in CAMPOS)}


def consumo(sd, cache, agora=None):
    """Tokens da sessão: conversa principal, agentes avulsos e agentes de cada workflow, por modelo; tempo somado
    dos agentes (primeiro ao último timestamp de cada um) e tempo real desde o começo da conversa principal."""
    agora = agora or time.time()
    arqs = [("principal", None, sd + ".jsonl")] + [("avulsos", None, p) for p in glob.glob(sd + "/subagents/agent-*.jsonl")] \
        + [("workflows", p.split("/")[-2], p) for p in glob.glob(sd + "/subagents/workflows/wf_*/agent-*.jsonl")]
    origens, wfs, modelos, total, por_agente = {}, {}, {}, _zero(), {}
    agentes_s, ini_principal = 0, None
    for origem, wid, p in arqs:
        try:
            cache[p] = ler_uso(cache.get(p), p)
        except OSError:
            continue
        e = cache[p]
        dur = (e["fim"] - e["ini"]) if e["ini"] is not None else 0
        o = origens.setdefault(origem, {"origem": origem, **_zero(), "arquivos": 0, "segundos": 0})
        _somar(total, e["tot"])
        for k in e["tot"]:
            o[k] += e["tot"][k]
        o["arquivos"] += 1
        o["segundos"] += dur
        for mod, t in e["modelos"].items():
            _somar(modelos.setdefault(mod, _zero()), t)
        if origem == "principal":
            ini_principal = e["ini"]
        else:
            por_agente[os.path.basename(p)[len("agent-"):-len(".jsonl")]] = sum(e["tot"].values())
            agentes_s += dur
        if wid:
            w = wfs.setdefault(wid, {"id": wid, **_zero(), "agentes": 0, "segundos": 0, "modelos": set(), "efforts": set(), "atividade": 0})
            for k in e["tot"]:
                w[k] += e["tot"][k]
            w["agentes"] += 1
            w["segundos"] += dur
            w["modelos"] |= set(e["modelos"])
            w["efforts"].add(effort_do_historico(p))
            w["atividade"] = max(w["atividade"], e["fim"] or 0)
    for w in wfs.values():
        w["nome"] = (_json(f"{sd}/workflows/{w['id']}.json", {}) or {}).get("workflowName") or w["id"]
        w["modelos"] = sorted(w["modelos"])
        w["efforts"] = efforts_ordenados(w["efforts"])
    return {
        "total": _com_total(total),
        "origens": [_com_total(origens[k]) for k in ("principal", "avulsos", "workflows") if k in origens],
        "workflows": sorted((_com_total(w) for w in wfs.values()), key=lambda w: w["atividade"], reverse=True),
        "modelos": {k: _com_total(v) for k, v in sorted(modelos.items(), key=lambda kv: -sum(kv[1].values()))},
        "agentes": por_agente,
        "agentes_segundos": agentes_s,
        "real_segundos": agora - ini_principal if ini_principal else 0,
        "inicio": ini_principal,
    }


def perguntas(cfg, arquivo):
    """perguntas.json (estruturadas) mais as abertas do duvidas.md que não estão nele. (lista, avisos)."""
    try:
        do_json, avisos = a.parse_perguntas(_ler(arquivo))
    except FileNotFoundError:
        do_json, avisos = [], []
    md = _ler_ou_vazio(_no_projeto(cfg, "arquivo_duvidas", "duvidas.md"))
    return a.mesclar_perguntas(do_json, md), avisos


def feitas_na_sessao(cfg, inicio, tarefas):
    """Tarefas citadas nos merges da dev desde o início da sessão (só lê o git)."""
    dos_merges = a.tarefas_dos_merges(_cmd(["git", "log", _ramo(cfg), "--merges", "-400", "--format=%ct|%s"], cfg["projeto"]), inicio)
    shas = [l.split()[1] for l in _cmd(["git", "log", _ramo(cfg), "-3000", "--format=%ct %H"], cfg["projeto"]).splitlines()
            if l.split()[0].isdigit() and int(l.split()[0]) >= inicio]
    return a.feitas_da_sessao(tarefas, dos_merges, inicio, shas)


def duracoes_baterias(caminhos):
    """Segundos do nascimento à última escrita de cada log (stat %W; 0 = o sistema não guarda nascimento)."""
    if not caminhos:
        return {}
    r = {}
    for l in _cmd(["stat", "-c", "%W %Y %n", "--", *caminhos]).splitlines():
        nasc, mod, nome = l.split(" ", 2)
        if int(nasc) > 0:
            r[nome] = int(mod) - int(nasc)
    return r


_tarefa_s = {}  # sha do merge -> segundos (o histórico não muda; evita um git por merge a cada leitura)


def duracao_passos(sd):
    """Segundos de cada agente terminado em workflow concluído (início = 1ª linha do jsonl, fim = última escrita)."""
    r = []
    for jp in sorted(glob.glob(sd + "/subagents/workflows/wf_*/journal.jsonl"), key=_mtime, reverse=True)[:30]:
        wid = os.path.basename(os.path.dirname(jp))
        if _json(f"{sd}/workflows/{wid}.json", {}).get("status") != "completed":
            continue
        for e in a.parse_journal(_ler(jp)):
            j = f"{os.path.dirname(jp)}/agent-{e['agentId']}.jsonl"
            ini = _inicio(j) if e["status"] == "terminado" and os.path.exists(j) else None
            if ini and _mtime(j) > ini:
                r.append(_mtime(j) - ini)
    return r


def duracoes_tarefas(cfg, inicio):
    """{id: segundos} do 1º commit da branch ao merge na dev, dos merges da sessão que citam uma só tarefa."""
    r = {}
    for l in _cmd(["git", "log", _ramo(cfg), "--merges", "-400", "--format=%h|%ct|%P|%s"], cfg["projeto"]).splitlines():
        h, ct, pais, assunto = l.split("|", 3)
        ids, p = re.findall(r"\bT(\d+)\b", assunto), pais.split()
        if not ct.isdigit() or int(ct) < inicio or len(set(ids)) != 1 or len(p) < 2:
            continue
        if h not in _tarefa_s:
            cts = [int(x) for x in _cmd(["git", "log", "--format=%ct", f"{p[0]}..{p[1]}"], cfg["projeto"]).split()]
            _tarefa_s[h] = int(ct) - min(cts) if cts else None
        if _tarefa_s[h] and _tarefa_s[h] > 0:
            r[int(ids[0])] = max(r.get(int(ids[0]), 0), _tarefa_s[h])
    return r


def duracao_baterias_verdes(cfg, bat_logs):
    """Duração das baterias verdes: logs reais (de 5 min para cima, as de código); sem nenhum, os registros do projeto."""
    v = [b["duracao"] for b in bat_logs if b["terminou"] and not b["falhou"] and (b.get("duracao") or 0) >= 300]
    if v:
        return v
    regs = glob.glob(os.path.join(_no_projeto(cfg, "registros_baterias", "registros/baterias"), "*.md"))
    return [d for d in (tempo.parse_registro(_ler(p)) for p in regs) if d]


def medidas_de_tempo(cfg, sd, con, bat):
    passos = duracao_passos(sd)
    conc = duracoes_tarefas(cfg, con["inicio"]) if con and con.get("inicio") else {}
    verdes = duracao_baterias_verdes(cfg, bat["logs"])
    rod = bat["rodando"]
    return {
        "passo_s": tempo.media(passos), "n_passos": len(passos), "bat_s": tempo.media(verdes), "n_bat": len(verdes),
        "tarefa_s": tempo.media(list(conc.values())), "n_tarefas": len(conc), "concluidas_s": conc,
        "frentes": max(1, round(con["agentes_segundos"] / con["real_segundos"])) if con and con.get("real_segundos") else 1,
        "fila": bat["fila"], "rodando": bool(rod), "bateria_desde": rod["desde"] if rod else None,
    }


# ---- Limites de uso (janela de 5 h e semana), gravados pela statusline.py ----
def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) != float("inf") else None


def _dic(x):
    return x if isinstance(x, dict) else {}


def _regressao(pontos):
    """Ritmo em %/s por mínimos quadrados e o ponto (t, pct) ajustado; None sem 2 pontos e 10 min de intervalo."""
    if len(pontos) < 2 or pontos[-1][0] - pontos[0][0] < 600:
        return None
    n = len(pontos)
    mt, mp = sum(p[0] for p in pontos) / n, sum(p[1] for p in pontos) / n
    vt = sum((p[0] - mt) ** 2 for p in pontos)
    return sum((p[0] - mt) * (p[1] - mp) for p in pontos) / vt if vt else None


def _janela_limite(sessoes, chave, dur, hist, hk, agora):
    melhor = None
    for t, j in sessoes:  # sessoes vem da mais recente para a mais antiga
        w = _dic(_dic(j.get("rate_limits")).get(chave))
        pct, rst = _num(w.get("used_percentage")), _num(w.get("resets_at"))
        if pct is not None and rst is not None:
            melhor = (t, pct, rst)
            break
    if not melhor or melhor[2] <= agora:
        return None
    t, pct, rst = melhor
    pts = [(h["t"], h[hk]) for h in hist if h["t"] >= rst - dur and h[hk] is not None]
    reg = _regressao(pts)
    ritmo, prev = None, None
    if reg is not None:
        ritmo = round(reg * 3600, 2)
        if reg > 0:
            quando = max(t, pts[-1][0]) + (100 - pct) / reg
            prev = quando if quando <= rst else None
    passo = -(-len(pts) // 200) or 1
    serie = [[p[0], p[1]] for p in pts[::passo]]
    if pts and serie[-1][0] != pts[-1][0]:
        serie.append([pts[-1][0], pts[-1][1]])
    return {"pct": pct, "reset_em": rst, "falta_segundos": max(0, rst - agora), "atualizado_em": t,
            "previsao_100_em": prev, "ritmo_pct_por_hora": ritmo, "serie": serie}


def _historico_limites(dir_):
    try:
        ls = _ler(os.path.join(dir_, "historico.jsonl"), 512_000).splitlines()
    except OSError:
        return []
    out = []
    for l in ls:
        try:
            h = json.loads(l)
        except ValueError:
            continue
        if isinstance(h, dict) and _num(h.get("t")) is not None:
            out.append({"t": h["t"], "h5": _num(h.get("h5")), "sem": _num(h.get("sem"))})
    return sorted(out, key=lambda h: h["t"])


def limites(cfg):
    agora = time.time()
    dir_ = os.path.expanduser(cfg.get("limites") or "~/.cache/claude-limites")
    arqs = []
    for p in glob.glob(os.path.join(dir_, "sessoes", "*.json")):
        m = _mtime(p)
        if agora - m <= 7 * 86400:
            arqs.append((m, p))
    sessoes = []
    for m, p in sorted(arqs, reverse=True)[:10]:
        j = _json(p)
        if isinstance(j, dict):
            sessoes.append((_num(j.get("gravado_em")) or m, j))
    sessoes.sort(key=lambda x: x[0], reverse=True)
    hist = _historico_limites(dir_)
    lista = []
    for t, j in sessoes:
        c, ctx, cwd = _dic(j.get("cost")), _dic(j.get("context_window")), j.get("cwd")
        mod = j.get("modelo")
        mod = _dic(mod).get("display_name") or _dic(mod).get("id") if isinstance(mod, dict) else mod
        lista.append({
            "session_id_curto": str(j.get("session_id") or "")[:8],
            "cwd_curto": "/".join(cwd.rstrip("/").split("/")[-2:]) if isinstance(cwd, str) else None,
            "modelo": mod if isinstance(mod, str) else None,
            "versao": j.get("versao") if isinstance(j.get("versao"), str) else None,
            "contexto_pct": _num(ctx.get("used_percentage")), "contexto_tamanho": _num(ctx.get("context_window_size")),
            "tokens_entrada": _num(ctx.get("total_input_tokens")), "tokens_saida": _num(ctx.get("total_output_tokens")),
            "custo_usd": _num(c.get("total_cost_usd")), "duracao_ms": _num(c.get("total_duration_ms")),
            "duracao_api_ms": _num(c.get("total_api_duration_ms")),
            "linhas_mais": _num(c.get("total_lines_added")), "linhas_menos": _num(c.get("total_lines_removed")),
            "atualizado_em": t})
    return {"janelas": {"cinco_horas": _janela_limite(sessoes, "five_hour", 5 * 3600, hist, "h5", agora),
                        "semana": _janela_limite(sessoes, "seven_day", 7 * 86400, hist, "sem", agora)},
            "sessoes": lista, "fonte": "statusline", "ultima_leitura_em": agora}
