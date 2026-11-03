"""Analisadores puros (texto entra, dados saem). Sem I/O, para testar com exemplos."""
import hmac
import json
import re
import logging
import unicodedata

_log = logging.getLogger("painel.analisadores")
_avisados = {}

CONCLUIDA = re.compile(r"(?<!não )(?<!nao )\b(?:na `?(?:dev|main)\b|feita\b|publicada\b|no ar\b)", re.I)
ANDANDO = re.compile(r"em andamento|em implementa|em curso|andando", re.I)
BLOQUEADA = re.compile(r"espera|d[úu]vida|bloquead", re.I)
FILA_INICIO = re.compile(r"(registrada|planejada|proposta)\b", re.I)


def classificar_estado(texto):
    """O começo do texto manda; 'na dev' só conta como concluída se nada do começo disser outra coisa."""
    t = (texto or "").strip()
    if not t:
        return "desconhecido"
    if FILA_INICIO.match(t):
        return "fila"
    if ANDANDO.match(t):
        return "andando"
    if BLOQUEADA.match(t):
        return "bloqueada"
    if CONCLUIDA.search(t[:120]):
        return "concluida"
    if ANDANDO.search(t):
        return "andando"
    if BLOQUEADA.search(t):
        return "bloqueada"
    return "fila"


def parse_tasks(texto):
    """Uma entrada por tarefa (faixa 'T148 a T156' vira uma por número). Primeira ocorrência vale."""
    cab = re.compile(r"^#{2,3} T(\d+)(?:\s+a\s+T(\d+))?\s*[·:\-]\s*(.*)$")
    blocos, atual = [], None
    for linha in texto.splitlines():
        m = cab.match(linha)
        if m:
            atual = {"ini": int(m[1]), "fim": int(m[2] or m[1]), "titulo": m[3].strip(), "linhas": []}
            blocos.append(atual)
        elif linha.startswith("## ") or linha.startswith("### "):
            atual = None
        elif atual is not None:
            atual["linhas"].append(linha)
    vistos, saida = set(), []
    for b in blocos:
        est, ls = "", b["linhas"]
        for i, l in enumerate(ls):
            m = re.match(r"^- \*\*Estado:\*\*\s*(.*)$", l)
            if m:
                est = m[1].strip()
                j = i + 1  # estado pode continuar nas linhas de baixo
                while j < len(ls) and ls[j].strip() and not ls[j].lstrip().startswith("- **"):
                    est = (est + " " + ls[j].strip()).strip()
                    j += 1
                break
        est = est.replace("**", "")
        fim = b["fim"] if 0 <= b["fim"] - b["ini"] <= 20 else b["ini"]
        for n in range(b["ini"], fim + 1):
            if n in vistos:
                continue
            vistos.add(n)
            saida.append({"id": n, "titulo": b["titulo"], "estado_texto": est, "estado": classificar_estado(est)})
    return saida


def _itens(linhas):
    """Bullets '- ...' do bloco, cada um com as linhas de continuação juntadas."""
    itens = []
    for l in linhas:
        if l.startswith("- "):
            itens.append(l[2:].strip())
        elif l.startswith("  ") and itens and l.strip():
            itens[-1] += " " + l.strip()
    return itens


def _opcoes(itens):
    """Só de um bloco explícito: item 'Opções: (a) ...; (b) ...' ou itens '(a) ...', '(b) ...' no começo da linha.
    '(a)/(b)' no meio de outro texto (correções já feitas) não é escolha. 'recomend' no trecho marca a recomendada."""
    limpos = [it.replace("**", "") for it in itens]
    corpo = next((it[it.index("(a)"):] for it in limpos
                  if re.match(r"Op[çc][õo]es:", it, re.I) and "(a)" in it and "(b)" in it), None)
    if corpo is None:
        lista = [it for it in limpos if re.match(r"\([a-e]\)\s", it)]
        corpo = " ".join(lista)
        if not lista[:1] or not lista[0].startswith("(a)") or "(b)" not in corpo:
            return []
    dita = re.search(r"\s*recomendad[ao]:?\s*\(([a-e])\)\.?", corpo, re.I)  # 'Recomendado: (a).' no fim
    if dita:
        corpo = corpo[:dita.start()] + corpo[dita.end():]
    saida = []
    for m in re.finditer(r"\(([a-e])\)\s*(.*?)(?=[;.,]?\s*\([a-e]\)\s|$)", corpo):
        txt = m[2].strip().rstrip(";")
        rec = dita[1] == m[1] if dita else "recomend" in txt.lower()
        txt = re.sub(r"^recomendad[ao]s?:\s*", "", txt, flags=re.I)
        saida.append({"letra": m[1], "texto": txt, "recomendada": rec})
    return saida


def _blocos_duvidas(texto):
    cab = re.compile(r"^### ([DP]-\d+[a-z]*)\.?\s*(.*)$")
    blocos, atual = [], None
    for l in texto.splitlines():
        m = cab.match(l)
        if m:
            atual = {"id": m[1], "titulo": m[2].strip(), "resp": False, "linhas": []}
            blocos.append(atual)
        elif l.startswith("## ") or l.startswith("### "):
            atual = None
        elif atual is not None:
            atual["resp"] |= "**Resposta" in l
            atual["linhas"].append(l)
    return blocos


def parse_duvidas(texto):
    """Dúvidas abertas: '### D-n.' ou '### P-n.' sem '**Resposta' no bloco, com situação e opções."""
    saida = []
    blocos = _blocos_duvidas(texto)
    rep = sorted({b["id"] for b in blocos if sum(x["id"] == b["id"] for x in blocos) > 1})
    if rep and tuple(rep) != _avisados.get("rep"):  # a cada leitura repetiria: avisa só quando muda
        _avisados["rep"] = tuple(rep)
        _log.warning("duvidas.md: id repetido (mostradas sem fundir): %s", ", ".join(rep))
    for b in blocos:
        if b["resp"]:
            continue
        itens = [i.replace("**", "") for i in _itens(b["linhas"])]
        sit = next((i[len("Situação:"):].strip() for i in itens if i.startswith("Situação:")), " ".join(itens))
        saida.append({"id": b["id"], "titulo": b["titulo"], "situacao": sit[:900], "opcoes": _opcoes(_itens(b["linhas"]))})
    return saida


def _str(x, maximo):
    return isinstance(x, str) and 0 < len(x.strip()) <= maximo and _texto_limpo(x)


def parse_perguntas(texto):
    """perguntas.json -> (perguntas válidas, avisos). Entrada inválida sai com aviso; recomendada vem primeiro."""
    try:
        bruto = json.loads(texto)
    except ValueError as e:
        return [], [f"perguntas.json inválido: {e}"]
    if not isinstance(bruto, list):
        return [], ["perguntas.json precisa ser uma lista"]
    saida, avisos, vistos = [], [], set()
    for i, q in enumerate(bruto):
        ops = q.get("opcoes") if isinstance(q, dict) else None
        ok = (isinstance(q, dict) and isinstance(q.get("id"), str) and re.fullmatch(r"[\w.-]{1,40}", q["id"])
              and q["id"] not in vistos and _str(q.get("pergunta"), 2000) and isinstance(ops, list) and 0 < len(ops) <= 12
              and all(isinstance(o, dict) and _str(o.get("rotulo"), 200) for o in ops)
              and len({o["rotulo"] for o in ops}) == len(ops)
              and all(isinstance(o.get("descricao", ""), str) for o in ops)
              and (q.get("header") is None or _str(q["header"], 60))
              and isinstance(q.get("contexto", ""), str) and isinstance(q.get("multiplas", False), bool))
        if not ok:
            avisos.append(f"perguntas.json: entrada {i} ignorada (precisa de id, pergunta e opcoes com rotulo único)")
            continue
        vistos.add(q["id"])
        opcoes = [{"rotulo": o["rotulo"].strip(), "descricao": o.get("descricao", "")[:600], "recomendada": o.get("recomendada") is True}
                  for o in ops]
        opcoes.sort(key=lambda o: not o["recomendada"])  # sort estável: a ordem dada vale entre as outras
        saida.append({"id": q["id"], "titulo": (q.get("header") or q["id"]).strip(), "header": (q.get("header") or q["id"]).strip(),
                      "pergunta": q["pergunta"].strip(), "contexto": q.get("contexto", "")[:2000],
                      "multiplas": q.get("multiplas", False), "opcoes": opcoes, "fonte": "json"})
    return saida, avisos


def mesclar_perguntas(do_json, texto_md):
    """As do perguntas.json (menos as já respondidas no duvidas.md) e, depois, as abertas do duvidas.md que não estão nele."""
    respondidas = {b["id"] for b in _blocos_duvidas(texto_md) if b["resp"]}
    saida = [q for q in do_json if q["id"] not in respondidas]
    ids = {q["id"] for q in saida} | {q["id"] for q in do_json}
    for d in parse_duvidas(texto_md):
        if d["id"] in ids:
            continue
        ops = [{**o, "rotulo": o["texto"], "descricao": ""} for o in d["opcoes"]] or [
            {"letra": "confirmo", "texto": "Confirmo", "rotulo": "Confirmo", "descricao": "", "recomendada": True},
            {"letra": "mudar", "texto": "Quero mudar algo", "rotulo": "Quero mudar algo",
             "descricao": "escreva o que mudar em Outro", "recomendada": False}]
        ops.sort(key=lambda o: not o["recomendada"])
        saida.append({**d, "header": d["id"], "pergunta": d["titulo"], "contexto": d["situacao"], "multiplas": False,
                      "opcoes": ops, "fonte": "md"})
    return saida


def parse_avisos(texto, secao="## Avisar"):
    """Itens da seção de avisos do arquivo de dúvidas (a que começa com `secao`)."""
    linhas, dentro = [], False
    for l in texto.splitlines():
        if l.startswith("## "):
            dentro = l.startswith(secao)
        elif dentro:
            linhas.append(l)
    return _itens(linhas)


def parse_journal(texto):
    ag = {}
    for linha in texto.splitlines():
        try:
            e = json.loads(linha)
        except ValueError:
            continue
        if not isinstance(e, dict) or not e.get("agentId"):
            continue
        d = ag.setdefault(e["agentId"], {"agentId": e["agentId"], "label": "", "fase": "", "status": "rodando", "resumo": ""})
        if e.get("type") == "started":
            d["label"], d["fase"] = e.get("label", ""), e.get("phase", "")
        elif e.get("type") == "result":
            d["status"] = "terminado"
            r = e.get("result")
            if isinstance(r, dict):
                d["resumo"] = str(r.get("status") or r.get("veredito") or "")
    return list(ag.values())


def parse_cadeia(texto):
    c = {"resultados": [], "na_dev": [], "parou": None}
    for l in texto.splitlines():
        if m := re.match(r"^== (\S+) saida=(\d+)", l):
            c["resultados"].append({"wt": m[1], "saida": int(m[2])})
        elif m := re.match(r"^(\S+): na dev \((\w+)", l):
            c["na_dev"].append({"wt": m[1], "sha": m[2]})
        elif m := re.match(r"^PAREI em (\S+)", l):
            c["parou"] = m[1]
    return c


def parse_bateria(texto):
    b = {"passo": "", "tela_feitos": 0, "tela_falhas": 0, "resumo": [], "terminou": False}
    resumo = False
    for l in texto.splitlines():
        if l.startswith("::: "):
            b["passo"] = l[4:].strip()
        elif l.startswith("=== resumo"):
            resumo = True
        elif m := re.match(r"^\s*([✓✘])\s+(\d+)\s+\[", l):
            b["tela_feitos"] = max(b["tela_feitos"], int(m[2]))
            b["tela_falhas"] += m[1] == "✘"
        elif resumo and (m := re.match(r"^(OK|FALHOU|PULADO)\s\s(.*)$", l)):
            b["resumo"].append({"status": m[1], "nome": m[2].strip()})
    b["terminou"] = resumo
    return b


def numero_da_tarefa(nome):
    m = re.search(r"(?:^|[/_\-])t(\d+)[a-z]?(?=$|[/_\-])", nome or "", re.I)
    return int(m[1]) if m else None


def melhor_worktree(lista, rodando):
    """Entre worktrees da mesma tarefa: o da bateria rodando, depois o que já andou (mais commits)."""
    return max(lista, key=lambda w: (w["nome"] == rodando, bool(w.get("a_frente") or w.get("mudancas_nao_commitadas")),
                                     w.get("a_frente") or 0, w.get("mudancas_nao_commitadas") or 0), default=None)


def ips_da_rede(saida_ip):
    """IPv4 das placas de rede (enp/wlp/eth/wl) na saída de 'ip -4 -o addr'; docker, br- e lo ficam fora."""
    return re.findall(r"^\d+:\s+(?:en|wl|eth)\w*\s+inet\s+([\d.]+)/", saida_ip, re.M)


def host_permitido(host, porta, nomes=()):
    """Contra DNS rebinding: só aceita o Host que o navegador usa para chegar aqui (local, IP da rede, nome da máquina)."""
    return host in {f"{n}:{porta}" for n in ("127.0.0.1", "localhost", *nomes)}


COOKIE = "painel_chave"


def chave_confere(dada, chave):
    if not dada or not chave:
        return False
    return hmac.compare_digest(dada.encode("utf-8", "replace"), chave.encode())


def acesso_liberado(ip, cookie_cab, chave):
    """De 127.0.0.1 sem chave; de qualquer outro endereço, só com o cookie da chave."""
    if ip == "127.0.0.1":
        return True
    # à mão, sem SimpleCookie: um cookie estranho de outro app no mesmo IP (JSON, espaço) derrubava o load
    for parte in (cookie_cab or "").split(";"):
        k, _, v = parte.strip().partition("=")
        if k == COOKIE:
            return chave_confere(v, chave)
    return False


def _texto_limpo(t):
    """Sem caractere de controle (só a quebra de linha) nem de formato invisível (direção, largura zero).
    O ZWJ (U+200D) passa: é o que junta os emoji compostos do teclado do celular."""
    return not any(unicodedata.category(c) in ("Cc", "Cf") and c not in "\n\u200d" for c in t)


def _texto_ok(t):
    return isinstance(t, str) and len(t) <= 2000 and _texto_limpo(t)


def validar_resposta(corpo, abertas):
    """(erro, None) ou (None, resposta limpa). Só dúvida aberta agora, opção dela, texto até 2000 caracteres.
    Dois formatos: {id, opcao: letra, texto} (o de antes) e {id, opcoes: [rótulos], outro?, texto?} (alternativas)."""
    if not isinstance(corpo, dict):
        return "corpo inválido", None
    d = next((x for x in abertas if isinstance(corpo.get("id"), str) and x["id"] == corpo["id"]), None)
    if not d:
        return "não é uma dúvida aberta", None
    texto = corpo.get("texto", "")
    if not _texto_ok(texto):
        return "texto inválido (até 2000 caracteres, sem caractere de controle)", None
    texto = texto.strip()
    if "opcoes" in corpo:
        esc, outro = corpo["opcoes"], corpo.get("outro", "")
        rotulos = [o.get("rotulo", o.get("texto")) for o in d["opcoes"]]
        if not isinstance(esc, list) or len(esc) > len(rotulos) or not all(isinstance(x, str) and x in rotulos for x in esc) \
                or len(set(esc)) != len(esc):
            return "opção inválida", None
        if len(esc) > 1 and not d.get("multiplas"):
            return "esta pergunta aceita uma opção só", None
        if not _texto_ok(outro):
            return "texto de 'Outro' inválido (até 2000 caracteres, sem caractere de controle)", None
        outro = outro.strip()
        if not esc and not outro and not texto:
            return "escolha uma opção ou escreva a resposta", None
        return None, {"id": d["id"], "titulo": d["titulo"], "pergunta": d.get("pergunta", d["titulo"]),
                      "opcoes": [x for x in rotulos if x in esc], "outro": outro, "texto": texto}
    opcao = corpo.get("opcao")
    op = next((o for o in d["opcoes"] if "letra" in o and o["letra"] == opcao), None)
    if opcao is not None and not op:
        return "opção inválida", None
    if not op and not texto:
        return "escolha uma opção ou escreva a resposta", None
    if op and op["letra"] == "mudar" and not texto:
        return "escreva o que mudar", None
    return None, {"id": d["id"], "titulo": d["titulo"], "opcao": opcao, "opcao_texto": op["texto"] if op else None,
                  "texto": texto}


def iso_ts(s):
    from datetime import datetime
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def tarefas_dos_merges(linhas, inicio):
    """Ids Tn citados nos merges ("%ct|%s") feitos a partir do início da sessão."""
    ids = set()
    for l in linhas.splitlines():
        t, _, assunto = l.partition("|")
        if t.strip().isdigit() and int(t) >= inicio:
            ids |= {int(n) for n in re.findall(r"\bT(\d+)\b", assunto)}
    return ids


def feitas_da_sessao(tarefas, dos_merges, inicio, shas_da_dev):
    """{id: critério}: 'merge' (Tn no assunto), 'data' (Estado concluída com data dentro da sessão) ou 'sha'
    (Estado cita sha de commit da dev depois do início). shas_da_dev: hashes completos desses commits."""
    from datetime import datetime
    ini = datetime.fromtimestamp(inicio)
    dia0 = (ini.month, ini.day)
    r = {i: "merge" for i in dos_merges}
    for t in tarefas:
        if t.get("estado") != "concluida" or t.get("id") in r:
            continue
        txt = t.get("estado_texto") or ""
        m = re.search(r"\b(\d{1,2})º?/(\d{1,2})\b", txt)
        if m and (int(m[2]), int(m[1])) >= dia0:
            r[t["id"]] = "data"
        elif any(h.startswith(x) for x in re.findall(r"\b[0-9a-f]{7,40}\b", txt) for h in shas_da_dev):
            r[t["id"]] = "sha"
    return r


def previsao(tarefas, real_s, agentes_s, baterias_fila, bateria_s, fase_final_h, agora, feitas_na_sessao=None):
    """Estimativa em horas reais: ritmo medido (tempo real / concluídas) × restantes, mais a fila de baterias
    pela mediana medida, mais a fase final (revisões e publicação) do config. Bloqueada fica fora e é dita."""
    conc = sum(t["estado"] == "concluida" for t in tarefas)
    bloq = sum(t["estado"] == "bloqueada" for t in tarefas)
    rest = len(tarefas) - conc - bloq
    paralelo = agentes_s / real_s if real_s else 0
    # o ritmo só conta o que saiu nesta sessão (merge na dev depois do início); as de sessões anteriores inflariam o ritmo
    if feitas_na_sessao is not None:
        conc = sum(t["estado"] == "concluida" and t.get("id") in feitas_na_sessao for t in tarefas)
    crit = ""
    if isinstance(feitas_na_sessao, dict):
        v = [feitas_na_sessao.get(t.get("id")) for t in tarefas if t["estado"] == "concluida"]
        crit = f" ({v.count('merge')} por merge, {v.count('data')} pelo Estado datado, {v.count('sha')} por sha da dev)"
    base = [f"{conc} tarefa(s) concluída(s) desta sessão{crit} em {real_s / 3600:.1f} h reais,"
            " contando o tempo parado"
            + (f" ({agentes_s / 3600:.1f} h de agentes somadas, {paralelo:.1f} frente(s) em paralelo em média)" if agentes_s else ""),
            f"{rest} tarefa(s) por fazer" + (f"; {bloq} bloqueada(s) ficam fora da conta" if bloq else "")]
    if not conc or not real_s:
        base.append("sem tarefa concluída nesta sessão ainda: sem ritmo medido para estimar")
        return {"horas": None, "conclusao_em": None, "restantes": rest, "bloqueadas": bloq, "paralelo": paralelo, "base": base}
    por = real_s / conc
    med = sorted(bateria_s)[len(bateria_s) // 2] if bateria_s else 0
    h_tar, h_bat = rest * por / 3600, baterias_fila * med / 3600
    base.append(f"ritmo medido: {por / 3600:.1f} h reais por tarefa → {h_tar:.1f} h")
    if baterias_fila:
        base.append(f"{baterias_fila} bateria(s) na fila × mediana de {med / 60:.0f} min das baterias verdes → {h_bat:.1f} h"
                    if med else f"{baterias_fila} bateria(s) na fila, sem bateria verde medida para estimar")
    base.append(f"fase final (revisões e publicação), valor do config: {fase_final_h:g} h")
    horas = h_tar + h_bat + fase_final_h
    return {"horas": horas, "conclusao_em": agora + round(horas * 3600), "restantes": rest, "bloqueadas": bloq,
            "paralelo": paralelo, "base": base}


def percentual(estado, wt=None, workflow=None, bateria_rodando=False):
    """Heurística: concluída 100; bateria rodando 90; workflow pela fração; branch à frente 85; fila 0."""
    if estado == "concluida":
        return 100
    if estado in ("fila", "desconhecido", "bloqueada"):
        return 0
    if bateria_rodando:
        return 90
    if workflow and workflow[1]:
        return min(95, round(100 * workflow[0] / workflow[1]))
    if wt and wt.get("a_frente"):
        return 85
    return 40


def status_workflow(status_json, mtime_journal, mtime_json):
    """O .json só é regravado quando o workflow termina; journal mais novo = foi retomado, status velho."""
    return None if status_json and mtime_journal > mtime_json else status_json


def estado_efetivo(estado, wt, workflow_rodando):
    """Worktree na dev, limpo e sem workflow = concluída; workflow rodando, worktree na dev ou commits à frente = andando."""
    if estado not in ("fila", "desconhecido", "andando"):
        return estado
    if wt and wt.get("na_dev") and not wt.get("mudancas_nao_commitadas") and not workflow_rodando:
        return "concluida"
    if workflow_rodando or (wt and (wt.get("na_dev") or wt.get("a_frente"))):
        return "andando"
    return estado
