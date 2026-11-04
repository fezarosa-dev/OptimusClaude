#!/usr/bin/env python3
"""Painel da sessão: lê o projeto e a sessão, escreve só em respostas/. De 127.0.0.1 sem chave; da rede, com a chave."""
import json
import os
import secrets
import socket
import subprocess
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import analisadores as a
import fontes
import linhas
import shells
import tempo
import workflows

AQUI = os.path.dirname(os.path.abspath(__file__))
_CFG_ARQ = os.path.join(AQUI, "config.json")
CFG = json.loads(Path(_CFG_ARQ if os.path.exists(_CFG_ARQ) else os.path.join(AQUI, "config.example.json")).read_text())  # o ativar.py grava o config.json
RESPOSTAS = os.path.join(AQUI, "respostas")
CHAVE_ARQ = os.path.join(AQUI, "chave.txt")
PERGUNTAS = os.path.join(AQUI, "perguntas.json")
CHAVE = ""  # carregada no __main__; vazia nunca libera acesso de fora
LIMITE_HORA = 30
_cache = {"t": 0, "v": None}
_trava = threading.Lock()
_git = {"t": 0, "v": None}
_nomes = {"t": 0, "v": ()}
_envios = deque()
_consumo = {"v": None, "erro": None, "cache": {}}
_shells = {"v": None, "erro": None, "cache": {}}
_lanc = {"v": None, "erro": None}
_linhas = {"v": None, "erro": None}
_acordar = {n: threading.Event() for n in ("consumo", "shells", "lancamentos", "linhas")}  # a rota de recarregar interrompe a espera de cada laço
_trava_envio = threading.Lock()
PAGINA_403 = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'><title>Sem acesso</title>"
              "<p>Sem acesso. Abra o endereço com a chave que o <code>iniciar.py</code> mostra no PC.</p>").encode()


def carregar_chave(caminho):
    """Gera na primeira vez (modo 600) e devolve a mesma nas seguintes."""
    try:
        fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return Path(caminho).read_text().strip()
    chave = secrets.token_urlsafe(24)
    with os.fdopen(fd, "w") as f:
        f.write(chave + "\n")
    return chave


def gravar_resposta(r, pasta):
    """Escreve num temporário e renomeia: quem lê pendentes/ nunca vê arquivo pela metade."""
    for sub in ("pendentes", "entregues"):
        os.makedirs(os.path.join(pasta, sub), mode=0o700, exist_ok=True)
    agora = time.time()
    nome = time.strftime("%Y%m%d-%H%M%S", time.localtime(agora)) + f"-{int(agora * 1e6) % 1_000_000:06d}-{r['id']}.json"
    fd, tmp = tempfile.mkstemp(dir=pasta, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(r, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(pasta, "pendentes", nome))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return nome


def nomes_da_maquina():
    """IPs da rede e o nome da máquina, para a conferência de Host; refeito a cada minuto (o DHCP muda o IP)."""
    if time.time() - _nomes["t"] > 60:
        try:
            ips = a.ips_da_rede(subprocess.run(["ip", "-4", "-o", "addr"], capture_output=True, text=True, timeout=3).stdout)
        except (OSError, subprocess.SubprocessError):
            ips = []
        _nomes["v"], _nomes["t"] = (*ips, socket.gethostname()), time.time()
    return _nomes["v"]


def _abertas():
    return fontes.perguntas(CFG, PERGUNTAS)[0]  # lido na hora: a dúvida pode ter sido respondida há pouco


def _vigiar_consumo():
    """Em segundo plano: a primeira leitura dos .jsonl leva segundos; depois só o que cresceu. /api/estado só lê o resultado."""
    while True:
        try:
            sd = fontes.sessao_dir(CFG)
            if sd:
                _consumo["v"], _consumo["erro"] = fontes.consumo(sd, _consumo["cache"]), None
        except Exception as e:
            _consumo["erro"] = f"{type(e).__name__}: {e}"
        _acordar["consumo"].wait(15)
        _acordar["consumo"].clear()


def _vigiar_shells():
    """Em segundo plano, como o consumo: a 1ª leitura dos .jsonl é lenta, depois só o que cresceu."""
    while True:
        try:
            _shells["v"], _shells["erro"] = shells.coletar(CFG, _shells["cache"], fontes.sessao_dir(CFG)), None
        except Exception as e:
            _shells["erro"] = f"{type(e).__name__}: {e}"
        _acordar["shells"].wait(4)
        _acordar["shells"].clear()


def _vigiar_lancamentos():
    """Em segundo plano: o que cresceu no .jsonl da sessão (args e início dos workflows lançados)."""
    while True:
        try:
            sd = fontes.sessao_dir(CFG)
            if sd:
                _lanc["v"], _lanc["erro"] = workflows.ler_lancamentos(_lanc["v"], sd + ".jsonl"), None
        except Exception as e:
            _lanc["erro"] = f"{type(e).__name__}: {e}"
        _acordar["lancamentos"].wait(4)
        _acordar["lancamentos"].clear()


def _vigiar_linhas():
    """Em segundo plano: git diff do ramo de integração contra o ramo base (e dos worktrees) a cada 60 s; erro do git vira aviso no quadro."""
    while True:
        try:
            _linhas["v"], _linhas["erro"] = linhas.coletar(CFG), None
        except Exception as e:
            _linhas["erro"] = f"{type(e).__name__}: {e}"
        _acordar["linhas"].wait(60)
        _acordar["linhas"].clear()


def recarregar():
    """Força repegar tudo: zera a validade dos caches e troca (nunca .clear()) os incrementais, que uma thread pode estar iterando."""
    _cache["t"] = _git["t"] = _nomes["t"] = fontes._docker_cache["t"] = 0
    _consumo["cache"], _shells["cache"], fontes._EFFORT, _lanc["v"] = {}, {}, {}, None
    for ev in _acordar.values():
        ev.set()


def _worktrees():
    # git status em todos os worktrees é caro e disputa lock: consulta no máximo a cada 15 s
    if time.time() - _git["t"] > 15:
        _git["v"], _git["t"] = fontes.git_worktrees(CFG), time.time()
    return _git["v"]


def _seguro(erros, nome, f, padrao=None):
    try:
        return f()
    except Exception as e:  # uma fonte que falha não derruba as outras
        erros[nome] = f"{type(e).__name__}: {e}"
        return padrao


def fase(est, ags, bat, wts):
    if bat["rodando"] or any(b["ativa"] for b in bat["logs"]):
        return "bateria rodando"
    if any(x["ativo"] for x in ags):
        return "implementando (agentes ativos)"
    if any(w["a_frente"] and not w["na_dev"] for w in wts):
        return "juntando na dev (branches prontas)"
    return "ocioso"


def _limites_mascarados(cfg):
    l = fontes.limites(cfg)
    for x in l["sessoes"]:  # cwd e modelo são texto de fora: passam pelo mesmo filtro do resto
        for k in ("cwd_curto", "modelo", "versao"):
            if x.get(k):
                x[k] = shells.mascarar(x[k])
    return l


def montar():
    erros, cfg = {}, CFG
    sd = _seguro(erros, "sessao", lambda: fontes.sessao_dir(cfg))
    wts = _seguro(erros, "worktrees", _worktrees, [])
    ags, wfs = _seguro(erros, "agentes", lambda: fontes.agentes_e_workflows(cfg, sd), ([], [])) if sd else ([], [])
    bat = _seguro(erros, "baterias", lambda: fontes.baterias(cfg, wts), {"rodando": None, "fila": [], "logs": [], "cadeia": {}})
    plan = _seguro(erros, "planejados", lambda: workflows.planejados(_lanc["v"]), {})
    for w in wfs:
        w["planejados"] = plan.get(w["id"])
    tar = _seguro(erros, "tarefas", lambda: fontes.tarefas(cfg, wts, wfs, bat), [])
    con0 = _consumo["v"]
    med = _seguro(erros, "tempo", lambda: fontes.medidas_de_tempo(cfg, sd, con0, bat), None) if sd else None
    if med:
        agora = time.time()
        for t in tar:
            t["tempo"] = tempo.estimar(t, med, agora)
    cont = {}
    for t in tar:
        cont[t["estado"]] = cont.get(t["estado"], 0) + 1
    # média do andamento de cada tarefa: contar só as concluídas deixava o anel parado enquanto o trabalho andava
    pct = round(sum(t.get("percentual") or 0 for t in tar) / len(tar)) if tar else 0
    perg, avisos_perg = _seguro(erros, "perguntas", lambda: fontes.perguntas(cfg, PERGUNTAS), ([], []))
    con = _consumo["v"]
    if _consumo["erro"]:
        erros["consumo"] = _consumo["erro"]
    if _shells["erro"]:
        erros["shells"] = _shells["erro"]
    if _lanc["erro"]:
        erros["lancamentos"] = _lanc["erro"]
    if _linhas["erro"]:
        erros["linhas"] = _linhas["erro"]
    prev = None
    if con:
        verdes = [b["duracao"] for b in bat["logs"] if b["terminou"] and not b["falhou"] and (b.get("duracao") or 0) >= 300]
        prev = _seguro(erros, "previsao", lambda: a.previsao(
            tar, con["real_segundos"], con["agentes_segundos"], len(bat["fila"]) + bool(bat["rodando"]), verdes,
            cfg.get("fase_final_horas", 2), time.time(),
            fontes.feitas_na_sessao(cfg, con["inicio"], tar) if con.get("inicio") else None))
    return {
        "gerado_em": time.time(),
        "sessao": {"id": os.path.basename(sd) if sd else None, "agentes_ativos": sum(x["ativo"] for x in ags)},
        "geral": {"fase": fase(None, ags, bat, wts), "percentual": pct, "total": len(tar), "contagem": cont,
                  "leva_a_partir_de": cfg["leva_a_partir_de"]},
        "perguntas": {"lista": perg, "avisos": avisos_perg}, "consumo": con, "previsao": prev,
        "rodando_agora": shells.quadro(_shells["v"], bat, ags, wfs),
        "quadro_workflows": _seguro(erros, "quadro_workflows", lambda: workflows.coletar(sd, wfs, ags, _lanc["v"], con, time.time(), cfg["ativo_segundos"], cfg["projeto"]),
                                    {"rodando": [], "recentes": []}) if sd else {"rodando": [], "recentes": []},
        "quadro_linhas": _linhas["v"],
        "tarefas": tar, "agentes": ags, "workflows": wfs, "worktrees": wts, "baterias": bat,
        "merges": _seguro(erros, "merges", lambda: fontes.git_merges(cfg), []),
        "duvidas": _seguro(erros, "duvidas", lambda: fontes.duvidas(cfg), {"abertas": [], "avisos": []}),
        "respostas": _seguro(erros, "respostas", lambda: fontes.respostas(RESPOSTAS), {"pendentes": [], "entregues": []}),
        "publicacao": _seguro(erros, "publicacao", lambda: fontes.publicacao(cfg), {}),
        "ambiente": _seguro(erros, "ambiente", lambda: fontes.ambiente(cfg), {}),
        "limites": _seguro(erros, "limites", lambda: _limites_mascarados(cfg), None),
        "erros": erros,
    }


def estado():
    with _trava:
        if time.time() - _cache["t"] > 3:
            _cache["v"], _cache["t"] = montar(), time.time()
        return _cache["v"]


ESTATICOS = {"/": ("index.html", "text/html; charset=utf-8"), "/ordenar.js": ("ordenar.js", "text/javascript; charset=utf-8")}


class H(BaseHTTPRequestHandler):
    timeout = 15  # conexão parada da rede não segura uma thread para sempre
    server_version, sys_version = "painel", ""

    def _enviar(self, codigo, corpo, tipo="application/json; charset=utf-8", extra=()):
        self.send_response(codigo)
        for k, v in (("Content-Type", tipo), ("Content-Length", str(len(corpo))), ("Cache-Control", "no-store"),
                     ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"),
                     ("Content-Security-Policy", "frame-ancestors 'none'"), *extra):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, codigo, obj):
        self._enviar(codigo, json.dumps(obj, ensure_ascii=False).encode())

    def _negar(self):
        self._enviar(403, PAGINA_403, "text/html; charset=utf-8")

    def _host_ok(self):
        return a.host_permitido(self.headers.get("Host"), self.server.server_port, nomes_da_maquina())

    def _acesso_ok(self):
        return a.acesso_liberado(self.client_address[0], self.headers.get("Cookie"), CHAVE)

    def do_GET(self):
        if not self._host_ok():
            return self._negar()
        p, _, q = self.path.partition("?")
        dada = parse_qs(q).get("chave")
        if dada is not None:  # primeiro acesso do celular: troca a chave da URL por cookie e limpa a URL
            if not a.chave_confere(dada[0], CHAVE):
                return self._negar()
            # Lax: o link aberto de outro app (WhatsApp) já entra; o POST segue protegido por X-Painel e Origin
            ck = f"{a.COOKIE}={CHAVE}; HttpOnly; SameSite=Lax; Path=/; Max-Age=31536000"
            return self._enviar(302, b"", "text/plain", (("Location", "/"), ("Set-Cookie", ck)))
        if not self._acesso_ok():
            return self._negar()
        if p == "/api/estado":
            return self._json(200, estado())
        if p in ESTATICOS:
            arq, tipo = ESTATICOS[p]
            return self._enviar(200, Path(AQUI, arq).read_bytes(), tipo)
        self.send_error(404)

    def do_POST(self):
        if not self._host_ok() or not self._acesso_ok():
            return self._negar()
        if self.path not in ("/api/responder", "/api/recarregar"):
            return self.send_error(404)
        # cabeçalho próprio + JSON obrigam o navegador a perguntar antes (preflight), e sem CORS a resposta é não
        origem = self.headers.get("Origin")
        if self.headers.get("X-Painel") != "1" or (origem is not None and origem != "http://" + self.headers["Host"]):
            return self._negar()
        if self.path == "/api/recarregar":
            recarregar()
            return self._json(200, {"ok": True})
        if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
            return self._json(415, {"ok": False, "erro": "use application/json"})
        try:
            n = int(self.headers.get("Content-Length") or -1)
        except ValueError:
            n = -1
        if not 0 <= n <= 16384:
            return self._json(413, {"ok": False, "erro": "corpo grande demais"})
        try:
            dados = json.loads(self.rfile.read(n))
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"ok": False, "erro": "JSON inválido"})
        try:
            abertas = _abertas()
        except OSError as e:
            return self._json(503, {"ok": False, "erro": f"{CFG.get('arquivo_duvidas') or 'duvidas.md'}: {e.strerror}"})
        erro, limpo = a.validar_resposta(dados, abertas)
        if erro:
            return self._json(400, {"ok": False, "erro": erro})
        with _trava_envio:
            agora = time.time()
            while _envios and agora - _envios[0] > 3600:
                _envios.popleft()
            if len(_envios) >= LIMITE_HORA:
                return self._json(429, {"ok": False, "erro": f"limite de {LIMITE_HORA} respostas por hora"})
            limpo["enviada_em"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(agora))
            gravar_resposta(limpo, RESPOSTAS)
            _envios.append(agora)
        self._json(200, {"ok": True, "enviada_em": time.strftime("%H:%M", time.localtime(agora))})

    def log_message(self, *a):
        pass


def criar(endereco, porta):
    return ThreadingHTTPServer((endereco, porta), H)


if __name__ == "__main__":
    CHAVE = carregar_chave(CHAVE_ARQ)
    try:
        with open(PERGUNTAS, "x") as f:  # a sessão do Claude mantém; começa vazio
            f.write("[]\n")
    except FileExistsError:
        pass
    threading.Thread(target=_vigiar_consumo, daemon=True).start()
    threading.Thread(target=_vigiar_shells, daemon=True).start()
    threading.Thread(target=_vigiar_lancamentos, daemon=True).start()
    threading.Thread(target=_vigiar_linhas, daemon=True).start()
    porta = int(os.environ.get("PORTA") or CFG["porta"])
    endereco = os.environ.get("ESCUTAR") or CFG.get("escutar", "0.0.0.0")
    print(f"escutando em {endereco}:{porta}", flush=True)
    criar(endereco, porta).serve_forever()
