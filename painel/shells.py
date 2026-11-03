"""Shells em segundo plano da sessão do Claude Code: o que está rodando e o que terminou, com a descrição que a sessão escreveu.

Rodando: processos `zsh -c "source <snapshot> ... && eval '<comando>' ..."` cuja saída (fd 1) é um tasks/<id>.output.
Descrição, comando e fim: o .jsonl da sessão (lido só no que cresceu). Tudo que sai passa por mascarar()."""
import glob
import json
import os
import re
import shlex
import time

import analisadores as a

ULTIMAS = 8      # linhas de saída por shell
TERMINADOS = 10  # quantos terminados mostrar
CURTO = 5        # segundos: abaixo disso, sem descrição na sessão, o processo não é listado
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_FIM_EVAL = re.compile(r"\s*<\s*/dev/null\s*&&\s*pwd\s+-P\s*>\|\s*\S+\s*$")
PEDACO = 8 << 20      # bytes lidos do .jsonl por vez: há sessões de 100 MB e a máquina tem pouca RAM
LINHA_MAX = 4 << 20   # linha maior que isso (blobs de requisição) não interessa e é descartada sem guardar
_SAIDA = re.compile(r"\s*\[exited with code (\d+)\]\s*")


def extrair_comando(script):
    """O comando de dentro do `eval '...'` que o Claude Code monta; None se não for esse formato."""
    m = re.search(r"&&\s*eval\s+", script)
    if not m:
        return None
    resto = _FIM_EVAL.sub("", script[m.end():])
    try:
        return " ".join(shlex.split(resto))
    except ValueError:
        return resto.strip()


_CHAVE = r"(?:apikey|api[_-]?key|token|secret|senha|password|passwd|chave|key)"
_PADROES = [  # (regex, troca): a ordem importa; erra para o lado de mascarar demais
    (re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+@"), "***@"),
    (re.compile(r"(?i)(authorization[\"']?\s*[:=]\s*)(?:(?:bearer|basic|token)\s+)?[^\s\"']+"), r"\1***"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"), "Bearer ***"),
    (re.compile(r"eyJ[\w-]{5,}(?:\.[\w-]+)*"), "***"),
    (re.compile(r"\bsk-[\w-]{8,}|\bgh[pousr]_\w{10,}|\bgithub_pat_\w+|\bxox[abprs]-[\w-]+|\bAKIA[0-9A-Z]{16}\b"
                r"|\bsbp_\w{16,}|\bsb_(?:secret|publishable)_\w+"), "***"),
    (re.compile(rf"(?i)\b(\w*{_CHAVE}\w*)([\"']?\s*[:=]\s*)(?:\"[^\"\n]*\"|'[^'\n]*'|[^\s\"'&;,}}]+)"), r"\1\2***"),
    (re.compile(rf"(?i)(--?{_CHAVE}\s+)[^\s\"']+"), r"\1***"),
    (re.compile(r"(?i)\b(password|passwd|senha|secret)(\s+)[^\s\"']+"), r"\1\2***"),  # "password abc": sem = nem :
    (re.compile(r"(?<!\S)(-u|--user)([\s=]+)(?:\"[^\"\n:]*:[^\"\n]*\"|'[^'\n:]*:[^'\n]*'|[^\s:]*:\S*)"), r"\1\2***"),  # curl -u usuario:senha
    (re.compile(r"(?i)\b((?:set-)?cookie[\"']?\s*[:=]\s*)[^\n\"']+"), r"\1***"),
    (re.compile(r"(?i)(--cookie[\s=]+)(?:\"[^\"\n]*\"|'[^'\n]*'|\S+)"), r"\1***"),
    (re.compile(r"(?<!\S)(-p)(?=[A-Za-z0-9_'\"!@#$%^*])['\"]?[^\s'\"]+"), r"\1***"),  # mysql -psenha / -p'senha'
    (re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"), "***"),
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "***"),
    (re.compile(r"(?<!\d)\d{14}(?!\d)|(?<!\d)\d{11}(?!\d)"), "***"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "***@***"),
    (re.compile(r"(?<!\d)(?:\+?55[\s.-]?)?(?:\(\d{2}\)|\d{2})[\s.-]?9?\d{4}[-.\s]\d{4}(?!\d)"), "***"),
]
_LONGO = re.compile(r"(?<![\w/.+=-])[A-Za-z0-9_+=-]{40,}(?![\w/.+=-])")


def _longo(m):
    s = m[0]
    segredo = re.search(r"\d", s) and re.search(r"[A-Za-z]", s) and not re.fullmatch(r"[0-9a-f]{40}", s)  # sha do git não é segredo
    return "***" if segredo else s


_CHAVE_PRIVADA = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S)  # sem o fim (saída cortada): vai até o fim
_CABECALHO = re.compile(r"""(?<!\S)(-H|--header)([\s=]*)(\$?)(?:"([^"\n]*)"|'([^'\n]*)'|(\S+))""")
_INOFENSIVOS = {"content-type", "accept", "title", "tags", "prefer", "user-agent", "accept-language", "accept-encoding",
                "cache-control", "priority", "content-length", "host", "origin", "referer"}


def _cabecalho(m):
    valor = next((g for g in m.groups()[3:] if g is not None), "")
    nome, dois_pontos, _ = valor.partition(":")
    if not dois_pontos or nome.strip().lower() in _INOFENSIVOS:
        return m[0]
    aspas = '"' if m[4] is not None else "'" if m[5] is not None else ""
    return f"{m[1]}{m[2]}{m[3]}{aspas}{nome.strip()}: ***{aspas}"


def mascarar(texto):
    """Esconde o que tem cara de segredo ou de dado pessoal: o painel abre no celular pela rede."""
    texto = _CABECALHO.sub(_cabecalho, _CHAVE_PRIVADA.sub("***", str(texto or "")))
    for rx, troca in _PADROES:
        texto = rx.sub(troca, texto)
    return _LONGO.sub(_longo, texto)


def _textos(e):
    c = e.get("content")
    if not isinstance(c, str):
        c = (e.get("message") or {}).get("content")
    if isinstance(c, str):
        return [c]
    return [x.get("text") or (x.get("content") if isinstance(x.get("content"), str) else "") or ""
            for x in c or [] if isinstance(x, dict)]


_NOTA = re.compile(r"<task-id>(\w+)</task-id>.*?<status>(\w+)</status>\s*<summary>(.*?)</summary>", re.S)
_ID_FUNDO = re.compile(r"running in background with ID: (\w+)")


def ler_shells(est, caminho):
    """Lê só o que cresceu do .jsonl: shells em segundo plano (task_id -> descrição, comando, início) e avisos de fim."""
    return ler_incremental(est, caminho, lambda: {"usos": {}, "tasks": {}, "notas": {}}, lambda e, l: _linha(e, l))


def ler_incremental(est, caminho, novo, tratar):
    """Lê só o que cresceu do .jsonl e chama tratar(est, linha) em cada linha completa; novo() cria o estado do zero."""
    st = os.stat(caminho)
    if not est or est.get("ino") != st.st_ino or st.st_size < est["pos"]:
        est = {"ino": st.st_ino, "pos": 0, **novo()}
    if st.st_size == est["pos"]:
        return est
    falta = st.st_size - est["pos"]
    consumido, resto, descartado = 0, b"", 0  # consumido: até o último \n; descartado: bytes já jogados de uma linha maior que LINHA_MAX
    with open(caminho, "rb") as f:
        f.seek(est["pos"])
        while falta > 0:
            bloco = f.read(min(PEDACO, falta))
            if not bloco:
                break
            falta -= len(bloco)
            *completas, resto = (resto + bloco).split(b"\n")  # a linha pela metade fica para o próximo pedaço (ou leitura)
            if descartado:
                if not completas:
                    descartado, resto = descartado + len(resto), b""
                    continue
                consumido += descartado + len(completas[0]) + 1
                descartado, completas = 0, completas[1:]
            for linha in completas:
                tratar(est, linha)
                consumido += len(linha) + 1
            if len(resto) > LINHA_MAX:
                descartado, resto = len(resto), b""
    est["pos"] += consumido
    return est


def _linha(est, linha):
    if len(linha) > LINHA_MAX or linha.startswith(b'{"type":"api-request'):
        return
    if b"run_in_background" not in linha and b"background with ID" not in linha and b"task-notification" not in linha:
        return
    try:
        e = json.loads(linha)
        ts = a.iso_ts(e["timestamp"]) if e.get("timestamp") else 0
        c = (e.get("message") or {}).get("content")
        for b in c if isinstance(c, list) else []:
            if not isinstance(b, dict):
                continue
            inp = b.get("input") or {}
            if b.get("type") == "tool_use" and b.get("name") == "Bash" and inp.get("run_in_background"):
                est["usos"][b["id"]] = {"descricao": str(inp.get("description") or "")[:300],
                                        "comando": str(inp.get("command") or "")[:3000], "inicio": ts}
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in est["usos"]:
                m = _ID_FUNDO.search(" ".join(_textos({"content": b.get("content")})))
                if m:
                    est["tasks"][m[1]] = est["usos"].pop(b["tool_use_id"])
        if e.get("type") in ("queue-operation", "user"):  # aviso de verdade; citação em fala ou eco da requisição não vale
            for t in _textos(e):
                if t.lstrip().startswith("<task-notification>"):
                    for tid, status, resumo in _NOTA.findall(t):
                        if tid in est["tasks"]:
                            est["notas"][tid] = {"status": status, "resumo": resumo[:500], "quando": ts}
    except (ValueError, KeyError, TypeError, AttributeError):
        pass


def estado_terminado(saida, nota):
    """{estado, codigo, motivo} de um shell que não tem mais processo; None se nada diz que acabou."""
    ultima = next((l for l in reversed((saida or "").splitlines()) if l.strip()), "")  # só vale como última linha: o script pode imprimir o marcador
    codigos = _SAIDA.findall(ultima)
    if nota and nota["status"] == "killed":
        mem = "low on memory" in nota["resumo"]
        return {"estado": "memoria" if mem else "parado", "codigo": None,
                "motivo": "morto por falta de memória no sistema" if mem else "parado à força"}
    if codigos:
        c = int(codigos[-1])
        return {"estado": "terminou" if c == 0 else "falhou", "codigo": c, "motivo": ""}
    if nota and nota["status"] == "failed":
        m = re.search(r"exit code (\d+)", nota["resumo"])
        return {"estado": "falhou", "codigo": int(m[1]) if m else None, "motivo": ""}
    if nota and nota["status"] == "completed":
        return {"estado": "terminou", "codigo": 0, "motivo": ""}
    return None


def _cauda(caminho, maximo=8000):
    try:
        with open(caminho, "rb") as f:
            f.seek(0, 2)
            tam = f.tell()
            f.seek(max(0, tam - maximo))
            t = f.read().decode("utf-8", "replace")
    except OSError:
        return None
    if tam > maximo:
        t = t.partition("\n")[2]  # a 1ª linha é cortada no meio: pedaço de segredo não seria reconhecido
    return t


def _linhas(texto):
    ls = _CHAVE_PRIVADA.sub("***", _ANSI.sub("", texto or "")).replace("\r", "\n").split("\n")
    while ls and not ls[-1].strip():
        ls.pop()
    return [mascarar(l)[:300] for l in ls[-ULTIMAS:]]


def _arq(caminho, modo="r"):
    with open(caminho, modo) as f:
        return f.read()


def _mtime(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return 0


def _processos(cfg, proc, agora):
    """Shells de fundo vivos: {task_id: {pid, sessao, comando, segundos}}; o processo mais antigo de cada task."""
    rx = re.compile("^" + re.escape(cfg["saidas"]) + r"/([^/]+)/tasks/(\w+)\.output$")
    clk = os.sysconf("SC_CLK_TCK")
    try:
        up = float(_arq(f"{proc}/uptime").split()[0])
    except (OSError, ValueError, IndexError):
        return {}
    vivos = {}
    for pid in os.listdir(proc):
        if not pid.isdigit():
            continue
        try:
            argv = _arq(f"{proc}/{pid}/cmdline", "rb").decode("utf-8", "replace").split("\0")
            if len(argv) < 3 or argv[1] != "-c" or "shell-snapshots" not in argv[2]:
                continue
            m = rx.match(os.readlink(f"{proc}/{pid}/fd/1"))
            comando = extrair_comando(argv[2])
            if not m or comando is None:
                continue
            seg = up - int(_arq(f"{proc}/{pid}/stat").rsplit(")", 1)[1].split()[19]) / clk
        except (OSError, ValueError, IndexError):
            continue  # o processo acabou no meio da leitura, ou é de outro usuário
        if m[2] not in vivos or seg > vivos[m[2]]["segundos"]:
            vivos[m[2]] = {"pid": int(pid), "sessao": m[1], "comando": comando, "segundos": seg}
    return vivos


def coletar(cfg, cache, sd=None, proc="/proc", agora=None):
    """{rodando: [...], terminados: [...]}: a sessão `sd` mais as sessões que têm shell vivo."""
    agora = agora or time.time()
    vivos = _processos(cfg, proc, agora)
    sessoes = {v["sessao"] for v in vivos.values()} | ({os.path.basename(sd)} if sd else set())
    info = {}
    for sid in sessoes:
        p = f"{cfg['sessoes']}/{sid}.jsonl"
        try:
            cache[p] = ler_shells(cache.get(p), p)
        except OSError:
            continue
        info[sid] = cache[p]
    rodando = []
    for tid, v in vivos.items():
        t = (info.get(v["sessao"]) or {}).get("tasks", {}).get(tid)
        if not t and v["segundos"] < CURTO:
            continue  # comando de primeiro plano de um agente: dura segundos e não é o que se quer ver
        saida = _cauda(f"{cfg['saidas']}/{v['sessao']}/tasks/{tid}.output")
        t = t or {}
        rodando.append({"id": tid, "fundo": bool(t), "sessao": v["sessao"][:8], "pid": v["pid"], "descricao": mascarar(t.get("descricao")),
                        "comando": mascarar(v["comando"])[:3000], "segundos": v["segundos"], "desde": agora - v["segundos"],
                        "saida": _linhas(saida)})
    rodando.sort(key=lambda x: -x["segundos"])
    fim, achados = cache.setdefault("fim", {}), []
    for sid, est in info.items():
        for tid, t in est["tasks"].items():
            if tid in vivos:
                continue
            chave = (sid, tid)
            nota = est["notas"].get(tid)
            if chave not in fim or (nota and not fim[chave]["_nota"]):  # o aviso pode chegar depois do fim da saída: reavalia
                caminho = f"{cfg['saidas']}/{sid}/tasks/{tid}.output"
                texto = _cauda(caminho, 20000)
                r = estado_terminado(texto, nota)
                if not r:
                    continue  # nada diz que acabou (ou o arquivo sumiu): não se afirma
                quando = (nota or {}).get("quando") or _mtime(caminho)
                fim[chave] = {"_nota": bool(nota), "id": tid, "sessao": sid[:8], **r, "quando": quando,
                              "duracao": quando - t["inicio"] if t.get("inicio") and quando >= t["inicio"] else None,
                              "descricao": mascarar(t["descricao"]), "comando": mascarar(t["comando"])[:3000],
                              "saida": _linhas(texto)}
            achados.append({k: v for k, v in fim[chave].items() if k != "_nota"})
    achados.sort(key=lambda x: -x["quando"])
    return {"rodando": rodando, "terminados": achados[:TERMINADOS]}


def quadro(shells, bat, ags, wfs):
    """O bloco do /api/estado: shells, a bateria em andamento (com a etapa) e o resumo de agentes e workflows."""
    r = bat.get("rodando")
    passo = next((b["passo"] for b in bat.get("logs", []) if r and b["wt"] == r["wt"]), "")
    return {"shells": shells or {"rodando": [], "terminados": []},
            "bateria": {"wt": r["wt"], "desde": r["desde"], "passo": passo, "fila": bat.get("fila", [])} if r else None,
            "agentes_ativos": sum(bool(x["ativo"]) for x in ags), "workflows_rodando": sum(bool(w["rodando"]) for w in wfs)}
