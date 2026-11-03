import json
import os
import shutil
import tempfile
import threading
import time
import unittest

import fontes
import servidor as s

AGORA = time.time()


def sessao(sid="s1", t=None, h5=(20, 3600), sem=(40, 86400), **kw):
    j = {"gravado_em": AGORA if t is None else t, "session_id": sid, "cwd": "/home/x/projeto/app", "modelo": {"id": "m", "display_name": "Opus"},
         "versao": "2.1", "cost": {"total_cost_usd": 2.5, "total_duration_ms": 1000, "total_api_duration_ms": 500,
                                    "total_lines_added": 3, "total_lines_removed": 1},
         "context_window": {"used_percentage": 30, "context_window_size": 200000, "total_input_tokens": 10, "total_output_tokens": 20},
         "rate_limits": {}}
    if h5:
        j["rate_limits"]["five_hour"] = {"used_percentage": h5[0], "resets_at": AGORA + h5[1]}
    if sem:
        j["rate_limits"]["seven_day"] = {"used_percentage": sem[0], "resets_at": AGORA + sem[1]}
    j.update(kw)
    return j


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.cfg = {"limites": self.dir}

    def grava(self, j, nome=None, mtime=None):
        os.makedirs(os.path.join(self.dir, "sessoes"), exist_ok=True)
        p = os.path.join(self.dir, "sessoes", (nome or j["session_id"]) + ".json")
        with open(p, "w") as f:
            f.write(j if isinstance(j, str) else json.dumps(j))
        if mtime:
            os.utime(p, (mtime, mtime))

    def hist(self, linhas):
        with open(os.path.join(self.dir, "historico.jsonl"), "w") as f:
            for l in linhas:
                f.write((l if isinstance(l, str) else json.dumps(l)) + "\n")


class TestJanelas(Base):
    def test_sem_nada(self):
        r = fontes.limites({"limites": os.path.join(self.dir, "nao-existe")})
        self.assertEqual(r["janelas"], {"cinco_horas": None, "semana": None})
        self.assertEqual(r["sessoes"], [])
        self.assertEqual(r["fonte"], "statusline")

    def test_janelas_do_retrato_mais_recente(self):
        self.grava(sessao("velha", t=AGORA - 500, h5=(10, 3000)))
        self.grava(sessao("nova", t=AGORA - 5, h5=(55, 1800)))
        r = fontes.limites(self.cfg)
        c = r["janelas"]["cinco_horas"]
        self.assertEqual(c["pct"], 55)
        self.assertAlmostEqual(c["reset_em"], AGORA + 1800, delta=1)
        self.assertAlmostEqual(c["falta_segundos"], 1800, delta=5)
        self.assertAlmostEqual(c["atualizado_em"], AGORA - 5, delta=1)
        self.assertEqual(r["janelas"]["semana"]["pct"], 40)

    def test_janela_faltando_em_uma_sessao_usa_outra(self):
        self.grava(sessao("a", t=AGORA - 5, sem=None))
        self.grava(sessao("b", t=AGORA - 50, sem=(77, 5000)))
        r = fontes.limites(self.cfg)
        self.assertEqual(r["janelas"]["cinco_horas"]["pct"], 20)
        self.assertEqual(r["janelas"]["semana"]["pct"], 77)

    def test_janela_vencida_vira_null(self):
        self.grava(sessao(h5=(90, -10), sem=(10, 100)))
        r = fontes.limites(self.cfg)
        self.assertIsNone(r["janelas"]["cinco_horas"])
        self.assertEqual(r["janelas"]["semana"]["pct"], 10)

    def test_lixo_vira_null_sem_excecao(self):
        self.grava("{torto", nome="a")
        self.grava("[1]", nome="b")
        self.grava(sessao("c", rate_limits={"five_hour": {"used_percentage": "x", "resets_at": None}, "seven_day": 3}))
        self.grava(sessao("d", rate_limits="lixo", cost=[], context_window="a", modelo=3, cwd=5))
        self.hist(["{torto", "[]", json.dumps({"t": "a"})])
        r = fontes.limites(self.cfg)
        self.assertEqual(r["janelas"], {"cinco_horas": None, "semana": None})
        self.assertIsInstance(r["sessoes"], list)

    def test_cfg_sem_limites_usa_padrao_sem_quebrar(self):
        self.assertIn("janelas", fontes.limites({}))


class TestSerieERitmo(Base):
    def pontos(self, n, passo, pct0, delta, base=None):
        base = AGORA - n * passo if base is None else base
        return [{"t": base + i * passo, "h5": pct0 + i * delta, "h5_reset": AGORA + 3600, "sem": 10, "sem_reset": AGORA + 86400}
                for i in range(n)]

    def test_serie_recortada_pela_janela(self):
        self.grava(sessao(h5=(30, 3600), sem=(10, 86400)))
        fora = {"t": AGORA - 5 * 3600 - 1000, "h5": 99, "h5_reset": AGORA - 1000, "sem": 9, "sem_reset": AGORA + 86400}
        self.hist([fora] + self.pontos(3, 600, 10, 5))
        r = fontes.limites(self.cfg)
        serie = r["janelas"]["cinco_horas"]["serie"]
        self.assertEqual(len(serie), 3)
        self.assertEqual([p[1] for p in serie], [10, 15, 20])
        self.assertEqual(len(r["janelas"]["semana"]["serie"]), 4)  # semanal inclui o ponto de há 5 h

    def test_serie_limitada_a_200(self):
        self.grava(sessao(h5=(30, 3600)))
        self.hist(self.pontos(900, 10, 0, 0.01))
        s5 = fontes.limites(self.cfg)["janelas"]["cinco_horas"]["serie"]
        self.assertLessEqual(len(s5), 200)
        self.assertGreater(len(s5), 100)

    def test_ritmo_e_previsao_antes_do_reset(self):
        # 10 pontos a cada 5 min, +2 pontos por ponto => 24 %/h; último = 18 %
        pts = self.pontos(10, 300, 0, 2, base=AGORA - 2700)
        self.grava(sessao(h5=(18, 3600)))
        self.hist(pts)
        c = fontes.limites(self.cfg)["janelas"]["cinco_horas"]
        self.assertAlmostEqual(c["ritmo_pct_por_hora"], 24, delta=0.5)
        # faltam 82 pontos a 24 %/h = ~3,4 h = 12300 s, depois do reset (1 h): não chega a 100%
        self.assertIsNone(c["previsao_100_em"])

    def test_previsao_chega_antes_do_reset(self):
        pts = self.pontos(10, 300, 0, 5, base=AGORA - 2700)  # 60 %/h, último 45
        self.grava(sessao(h5=(45, 3600)))
        self.hist(pts)
        c = fontes.limites(self.cfg)["janelas"]["cinco_horas"]
        self.assertAlmostEqual(c["ritmo_pct_por_hora"], 60, delta=1)
        self.assertAlmostEqual(c["previsao_100_em"], AGORA + 55 / 60 * 3600, delta=120)

    def test_poucos_pontos_ou_intervalo_curto_sem_ritmo(self):
        self.grava(sessao(h5=(30, 3600)))
        self.hist(self.pontos(1, 300, 10, 1))
        c = fontes.limites(self.cfg)["janelas"]["cinco_horas"]
        self.assertIsNone(c["ritmo_pct_por_hora"])
        self.assertIsNone(c["previsao_100_em"])
        self.hist(self.pontos(5, 60, 10, 1, base=AGORA - 300))  # só 4 min
        self.assertIsNone(fontes.limites(self.cfg)["janelas"]["cinco_horas"]["ritmo_pct_por_hora"])

    def test_ritmo_negativo_sem_previsao(self):
        self.grava(sessao(h5=(30, 3600)))
        self.hist(self.pontos(10, 300, 50, -2, base=AGORA - 2700))
        c = fontes.limites(self.cfg)["janelas"]["cinco_horas"]
        self.assertLess(c["ritmo_pct_por_hora"], 0)
        self.assertIsNone(c["previsao_100_em"])


class TestSessoes(Base):
    def test_campos(self):
        self.grava(sessao("abcdef1234567890"))
        x = fontes.limites(self.cfg)["sessoes"][0]
        self.assertEqual(x["session_id_curto"], "abcdef12")
        self.assertEqual(x["cwd_curto"], "projeto/app")
        self.assertEqual(x["modelo"], "Opus")
        self.assertEqual(x["versao"], "2.1")
        self.assertEqual(x["contexto_pct"], 30)
        self.assertEqual(x["contexto_tamanho"], 200000)
        self.assertEqual((x["tokens_entrada"], x["tokens_saida"]), (10, 20))
        self.assertEqual(x["custo_usd"], 2.5)
        self.assertEqual((x["duracao_ms"], x["duracao_api_ms"], x["linhas_mais"], x["linhas_menos"]), (1000, 500, 3, 1))
        self.assertAlmostEqual(x["atualizado_em"], AGORA, delta=1)

    def test_ordem_limite_e_idade(self):
        for i in range(14):
            self.grava(sessao(f"s{i:02d}", t=AGORA - i * 10), mtime=AGORA - i * 10)
        self.grava(sessao("antiga", t=AGORA - 8 * 86400), mtime=AGORA - 8 * 86400)
        ss = fontes.limites(self.cfg)["sessoes"]
        self.assertEqual(len(ss), 10)
        self.assertEqual([x["session_id_curto"] for x in ss], [f"s{i:02d}" for i in range(10)])
        self.assertNotIn("antiga", [x["session_id_curto"] for x in ss])


class TestEstadoApi(Base):
    def test_montar_tem_limites_com_mascara(self):
        self.grava(sessao(cwd="/x/y", modelo={"display_name": "Opus"}, session_id="s1"))
        orig = s.CFG
        s.CFG = dict(orig, limites=self.dir)
        self.addCleanup(setattr, s, "CFG", orig)
        l = s.montar()["limites"]
        self.assertEqual(l["janelas"]["cinco_horas"]["pct"], 20)
        self.assertEqual(l["sessoes"][0]["cwd_curto"], "x/y")

    def test_mascara_segredo_no_cwd(self):
        self.grava(sessao(cwd="/x/token=abcdef1234567890abcdef"))
        orig = s.CFG
        s.CFG = dict(orig, limites=self.dir)
        self.addCleanup(setattr, s, "CFG", orig)
        self.assertNotIn("abcdef1234567890abcdef", json.dumps(s.montar()["limites"]))


if __name__ == "__main__":
    unittest.main()
