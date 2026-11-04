"""Servidor de verdade numa porta livre, em processo; o cliente remoto é o próprio PC pelo IP da rede."""
import http.client
import json
import os
import shutil
import stat
import sys
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

import analisadores as a
import fontes
import servidor as s

AQUI = os.path.dirname(os.path.abspath(__file__))
ABERTAS = [{"id": "D-29", "titulo": "Ordem", "situacao": "", "opcoes": [
    {"letra": "a", "texto": "x", "recomendada": True}, {"letra": "b", "texto": "y", "recomendada": False}]}]
IP_REDE = next(iter(a.ips_da_rede(subprocess.run(["ip", "-4", "-o", "addr"], capture_output=True, text=True).stdout)), None)


class Base(unittest.TestCase):
    endereco = "127.0.0.1"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig = (s.RESPOSTAS, s.CHAVE, s._abertas, s.estado)
        s.RESPOSTAS = os.path.join(self.tmp, "respostas")
        s.CHAVE = "chave-de-teste-" + "x" * 20
        s._abertas = lambda: ABERTAS
        s.estado = lambda: {"gerado_em": 1}
        s._envios.clear()
        self.srv = s.criar(self.endereco, 0)
        self.porta = self.srv.server_port
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        s.RESPOSTAS, s.CHAVE, s._abertas, s.estado = self.orig
        shutil.rmtree(self.tmp)

    def req(self, metodo, caminho, corpo=None, cab=None, host=None):
        c = http.client.HTTPConnection(self.endereco, self.porta, timeout=5)
        h = {"Host": host or f"{self.endereco}:{self.porta}"}
        h.update(cab or {})
        c.request(metodo, caminho, body=corpo, headers=h)
        r = c.getresponse()
        r.corpo = r.read().decode("utf-8", "replace")
        c.close()
        return r

    def post(self, dados, cab=None, **kw):
        h = {"Content-Type": "application/json", "X-Painel": "1"}
        h.update(cab or {})
        return self.req("POST", "/api/responder", json.dumps(dados), h, **kw)

    def pendentes(self):
        p = os.path.join(s.RESPOSTAS, "pendentes")
        return sorted(os.listdir(p)) if os.path.isdir(p) else []


class TestLocal(Base):
    def test_get_local_sem_chave(self):
        self.assertEqual(self.req("GET", "/").status, 200)
        self.assertEqual(self.req("GET", "/ordenar.js").status, 200)
        self.assertEqual(self.req("GET", "/api/estado").status, 200)

    def test_host_estranho(self):
        self.assertEqual(self.req("GET", "/", host="evil.com").status, 403)

    def test_sem_cors(self):
        r = self.req("GET", "/", cab={"Origin": "http://evil.com"})
        self.assertIsNone(r.getheader("Access-Control-Allow-Origin"))
        r = self.req("OPTIONS", "/api/responder", cab={"Origin": "http://evil.com"})
        self.assertGreaterEqual(r.status, 400)
        self.assertIsNone(r.getheader("Access-Control-Allow-Origin"))

    def test_post_valido_grava(self):
        r = self.post({"id": "D-29", "opcao": "a", "texto": "pode"}, {"Origin": f"http://127.0.0.1:{self.porta}"})
        self.assertEqual(r.status, 200, r.corpo)
        self.assertTrue(json.loads(r.corpo)["ok"])
        (nome,) = self.pendentes()
        self.assertTrue(nome.endswith("-D-29.json"))
        caminho = os.path.join(s.RESPOSTAS, "pendentes", nome)
        dado = json.loads(Path(caminho).read_text())
        self.assertEqual((dado["id"], dado["opcao"], dado["texto"]), ("D-29", "a", "pode"))
        self.assertEqual(stat.S_IMODE(os.stat(caminho).st_mode), 0o600)

    def test_post_recusas(self):
        ok = {"id": "D-29", "texto": "pode"}
        self.assertEqual(self.req("POST", "/api/responder", json.dumps(ok), {"Content-Type": "application/json"}).status, 403)
        self.assertEqual(self.post(ok, {"Content-Type": "text/plain"}).status, 415)
        self.assertEqual(self.post(ok, {"Origin": "http://evil.com"}).status, 403)
        self.assertEqual(self.post({"id": "D-99", "texto": "x"}).status, 400)
        self.assertEqual(self.post({"id": "D-29", "texto": "x" * 2001}).status, 400)
        self.assertEqual(self.post({"id": "D-29", "texto": "a\x07b"}).status, 400)
        self.assertEqual(self.req("POST", "/api/responder", "{nao json", {"Content-Type": "application/json", "X-Painel": "1"}).status, 400)
        self.assertEqual(self.req("POST", "/api/outra", "{}", {"Content-Type": "application/json", "X-Painel": "1"}).status, 404)
        self.assertEqual(self.pendentes(), [])

    def test_sem_duvidas_md_503(self):
        def some():
            raise FileNotFoundError(2, "No such file or directory")
        s._abertas = some
        r = self.post({"id": "D-29", "texto": "x"})
        self.assertEqual(r.status, 503)
        self.assertIn("duvidas.md", json.loads(r.corpo)["erro"])

    def test_limite_por_hora(self):
        for i in range(30):
            self.assertEqual(self.post({"id": "D-29", "texto": f"r{i}"}).status, 200)
        self.assertEqual(self.post({"id": "D-29", "texto": "a mais"}).status, 429)
        self.assertEqual(len(self.pendentes()), 30)


@unittest.skipUnless(IP_REDE, "máquina sem IP de rede")
class TestRemoto(Base):
    endereco = IP_REDE

    def test_sem_chave_403_sem_dado(self):
        for caminho in ("/", "/api/estado", "/ordenar.js", "/?chave=errada"):
            r = self.req("GET", caminho)
            self.assertEqual(r.status, 403, caminho)
            self.assertNotIn("<script", r.corpo)
            self.assertNotIn("gerado_em", r.corpo)
            self.assertLess(len(r.corpo), 600)

    def test_chave_grava_cookie_e_redireciona(self):
        r = self.req("GET", "/?chave=" + s.CHAVE)
        self.assertEqual(r.status, 302)
        self.assertEqual(r.getheader("Location"), "/")
        ck = r.getheader("Set-Cookie")
        for parte in ("painel_chave=", "HttpOnly", "SameSite=Lax", "Path=/"):
            self.assertIn(parte, ck)
        cookie = ck.split(";")[0]
        self.assertEqual(self.req("GET", "/", cab={"Cookie": cookie}).status, 200)
        self.assertEqual(self.req("GET", "/api/estado", cab={"Cookie": cookie}).status, 200)
        self.assertEqual(self.req("GET", "/", cab={"Cookie": "painel_chave=outra"}).status, 403)

    def test_post_exige_cookie(self):
        dados = {"id": "D-29", "texto": "pode"}
        self.assertEqual(self.post(dados).status, 403)
        self.assertEqual(self.post(dados, {"Cookie": "painel_chave=" + s.CHAVE}).status, 200)
        self.assertEqual(len(self.pendentes()), 1)

    def test_host_por_ip_e_nome(self):
        cab = {"Cookie": "painel_chave=" + s.CHAVE}
        self.assertEqual(self.req("GET", "/", cab=cab, host=f"{os.uname().nodename}:{self.porta}").status, 200)
        self.assertEqual(self.req("GET", "/", cab=cab, host=f"evil.com:{self.porta}").status, 403)


class TestChave(unittest.TestCase):
    def test_gera_uma_vez_com_modo_600(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "chave.txt")
            c1 = s.carregar_chave(p)
            self.assertGreaterEqual(len(c1), 32)
            self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)
            self.assertEqual(s.carregar_chave(p), c1)


class TestGravacaoAtomica(unittest.TestCase):
    def test_so_aparece_em_pendentes_pelo_rename(self):
        with tempfile.TemporaryDirectory() as d:
            renomeios = []
            orig = os.replace

            def falso(src, dst):
                self.assertFalse(os.listdir(os.path.join(d, "pendentes")))  # nada visível antes do rename
                renomeios.append(dst)
                orig(src, dst)

            os.replace = falso
            try:
                nome = s.gravar_resposta({"id": "D-1", "texto": "t"}, d)
            finally:
                os.replace = orig
            self.assertEqual(renomeios, [os.path.join(d, "pendentes", nome)])
            self.assertEqual(os.listdir(os.path.join(d, "pendentes")), [nome])
            self.assertEqual(sorted(os.listdir(d)), ["entregues", "pendentes"])  # temporário não sobra
            self.assertNotIn("\n", Path(d, "pendentes", nome).read_text())

    def test_listar_respostas(self):
        with tempfile.TemporaryDirectory() as d:
            s.gravar_resposta({"id": "D-1", "texto": "t", "enviada_em": "2026-11-01T10:00:00"}, d)
            r = fontes.respostas(d)
            self.assertEqual([x["id"] for x in r["pendentes"]], ["D-1"])
            self.assertEqual(r["entregues"], [])


class TestEsperarResposta(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        shutil.copy(os.path.join(AQUI, "esperar_resposta.py"), self.d)
        self.pend = os.path.join(self.d, "respostas", "pendentes")
        os.makedirs(self.pend)

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_entrega_o_mais_antigo_e_move(self):
        for nome, txt in (("20261101-100000-000001-D-1.json", '{"id": "D-1"}'), ("20261101-110000-000001-D-2.json", '{"id": "D-2"}')):
            Path(self.pend, nome).write_text(txt)
        r = subprocess.run([sys.executable, os.path.join(self.d, "esperar_resposta.py")], capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, 'RESPOSTA {"id": "D-1"}\n')
        self.assertEqual(os.listdir(self.pend), ["20261101-110000-000001-D-2.json"])
        self.assertEqual(os.listdir(os.path.join(self.d, "respostas", "entregues")), ["20261101-100000-000001-D-1.json"])

    def test_espera_ate_chegar(self):
        p = subprocess.Popen([sys.executable, os.path.join(self.d, "esperar_resposta.py")], stdout=subprocess.PIPE, text=True,
                             env={**os.environ, "INTERVALO": "0.2"})
        time.sleep(0.6)
        self.assertIsNone(p.poll())
        Path(self.pend, "x.json.tmp").write_text("{}")  # temporário não é resposta
        time.sleep(0.5)
        self.assertIsNone(p.poll())
        Path(self.pend, "20261101-100000-000001-D-3.json").write_text('{"id": "D-3"}')
        out, _ = p.communicate(timeout=5)
        self.assertEqual((p.returncode, out), (0, 'RESPOSTA {"id": "D-3"}\n'))


if __name__ == "__main__":
    unittest.main()
