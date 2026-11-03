import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import statusline as st

AQUI = os.path.dirname(os.path.abspath(__file__))
AGORA = 1_800_000_000


def dados(**kw):
    d = {"session_id": "abc-123", "transcript_path": "/x/segredo.jsonl", "cwd": "/a/b", "version": "2.1",
         "model": {"id": "m1", "display_name": "Opus"},
         "cost": {"total_cost_usd": 1.234, "total_duration_ms": 5000},
         "context_window": {"used_percentage": 34.4, "context_window_size": 200000},
         "exceeds_200k_tokens": False,
         "rate_limits": {"five_hour": {"used_percentage": 23, "resets_at": AGORA + 3600},
                         "seven_day": {"used_percentage": 41, "resets_at": AGORA + 86400}}}
    d.update(kw)
    return d


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def hist(self):
        p = os.path.join(self.dir, "historico.jsonl")
        return [json.loads(l) for l in Path(p).read_text().splitlines()] if os.path.exists(p) else []


class TestProcessar(Base):
    def test_grava_sessao_sem_transcript(self):
        linha = st.processar(dados(), self.dir, AGORA)
        p = os.path.join(self.dir, "sessoes", "abc-123.json")
        j = json.loads(Path(p).read_text())
        self.assertEqual(j["gravado_em"], AGORA)
        self.assertEqual(j["modelo"], {"id": "m1", "display_name": "Opus"})
        self.assertEqual(j["rate_limits"]["five_hour"]["used_percentage"], 23)
        self.assertNotIn("transcript_path", j)
        self.assertNotIn("segredo", Path(p).read_text())
        self.assertEqual(stat.S_IMODE(os.stat(self.dir).st_mode), 0o700)
        self.assertIn("5h 23%", linha)
        self.assertIn("semana 41%", linha)
        self.assertIn("contexto 34%", linha)
        self.assertIn("US$ 1,23", linha)
        self.assertEqual(os.listdir(os.path.join(self.dir, "sessoes")), ["abc-123.json"])  # sem .tmp sobrando

    def test_session_id_saneado(self):
        st.processar(dados(session_id="../../etc/x"), self.dir, AGORA)
        arqs = os.listdir(os.path.join(self.dir, "sessoes"))
        self.assertEqual(len(arqs), 1)
        self.assertNotIn("/", arqs[0])
        self.assertFalse(os.path.exists(os.path.join(self.dir, "..", "x.json")))

    def test_sem_rate_limits_nao_grava_historico(self):
        d = dados()
        del d["rate_limits"]
        linha = st.processar(d, self.dir, AGORA)
        self.assertEqual(self.hist(), [])
        self.assertNotIn("5h", linha)
        self.assertIn("contexto 34%", linha)

    def test_janela_faltando(self):
        d = dados()
        del d["rate_limits"]["seven_day"]
        linha = st.processar(d, self.dir, AGORA)
        self.assertIn("5h 23%", linha)
        self.assertNotIn("semana", linha)
        h = self.hist()
        self.assertEqual(h[0]["h5"], 23)
        self.assertIsNone(h[0]["sem"])

    def test_tipos_errados(self):
        d = dados(rate_limits={"five_hour": {"used_percentage": "x", "resets_at": []}, "seven_day": 7},
                  cost="a", context_window=[], model=5, cwd=3)
        linha = st.processar(d, self.dir, AGORA)
        self.assertIsInstance(linha, str)
        self.assertEqual(self.hist(), [])
        d = dados(rate_limits="lixo", session_id=None)
        st.processar(d, self.dir, AGORA)

    def test_historico_so_quando_muda(self):
        st.processar(dados(), self.dir, AGORA)
        st.processar(dados(), self.dir, AGORA + 5)
        self.assertEqual(len(self.hist()), 1)
        d = dados()
        d["rate_limits"]["five_hour"]["used_percentage"] = 24
        st.processar(d, self.dir, AGORA + 10)
        h = self.hist()
        self.assertEqual(len(h), 2)
        self.assertEqual(h[1], {"t": AGORA + 10, "h5": 24, "h5_reset": AGORA + 3600, "sem": 41, "sem_reset": AGORA + 86400})

    def test_rotacao_guarda_8_dias(self):
        p = os.path.join(self.dir, "historico.jsonl")
        velha = {"t": AGORA - 9 * 86400, "h5": 1, "h5_reset": 1, "sem": 1, "sem_reset": 1}
        nova = {"t": AGORA - 86400, "h5": 2, "h5_reset": 2, "sem": 2, "sem_reset": 2}
        with open(p, "w") as f:
            f.write(json.dumps(velha) + "\n")
            f.write(json.dumps(nova) + "\n")
            f.write(("x" * 100 + "\n") * 25000)  # passa de 2 MB; linha torta é descartada
            f.write(json.dumps({"t": AGORA - 10, "h5": 9, "h5_reset": AGORA + 3600, "sem": 41, "sem_reset": AGORA + 86400}) + "\n")
        self.assertGreater(os.path.getsize(p), 2_000_000)
        st.processar(dados(), self.dir, AGORA)
        h = self.hist()
        self.assertNotIn(velha, h)
        self.assertIn(nova, h)
        self.assertLess(os.path.getsize(p), 2_000_000)
        self.assertEqual(h[-1]["h5"], 23)

    def test_formato_horario_e_dia_da_semana(self):
        t = time.mktime((2026, 11, 7, 9, 0, 0, 0, 0, -1))  # sábado
        d = dados(rate_limits={"five_hour": {"used_percentage": 5, "resets_at": t},
                               "seven_day": {"used_percentage": 6, "resets_at": t}})
        linha = st.processar(d, self.dir, AGORA)
        self.assertIn("(volta 09:00)", linha)
        self.assertIn("(volta sáb 09:00)", linha)


class TestMain(Base):
    def rodar(self, entrada):
        env = dict(os.environ, CLAUDE_LIMITES_DIR=self.dir)
        return subprocess.run([sys.executable, os.path.join(AQUI, "statusline.py")], input=entrada,
                              capture_output=True, text=True, env=env)

    def test_vazio_e_invalido_saem_0(self):
        for e in ("", "   ", "{torto", "[1,2]", "null"):
            r = self.rodar(e)
            self.assertEqual(r.returncode, 0, e)
            self.assertTrue(r.stdout.strip(), e)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "sessoes")))

    def test_completo_via_stdin(self):
        r = self.rodar(json.dumps(dados(rate_limits={"five_hour": {"used_percentage": 10, "resets_at": time.time() + 600}})))
        self.assertEqual(r.returncode, 0)
        self.assertIn("5h 10%", r.stdout)
        self.assertEqual(len(r.stdout.strip().splitlines()), 1)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "sessoes", "abc-123.json")))

    def test_erro_ao_gravar_nao_derruba(self):
        arq = os.path.join(self.dir, "arquivo")
        open(arq, "w").close()
        env = dict(os.environ, CLAUDE_LIMITES_DIR=os.path.join(arq, "sub"))
        r = subprocess.run([sys.executable, os.path.join(AQUI, "statusline.py")], input=json.dumps(dados()),
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("5h", r.stdout)


if __name__ == "__main__":
    unittest.main()
