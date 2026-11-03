"""Teto de memória da sessão (somando o cgroup do Claude, a fatia de testes se configurada, e os contêineres)."""
import time
import unittest

import fontes

DOCKER = ['{"Name":"db","MemUsage":"512MiB / 1GiB"}',
          '{"Name":"rest","MemUsage":"100.5MiB / 192MiB"}',
          '{"Name":"studio","MemUsage":"50MiB / 13.28GiB"}']


class TestParse(unittest.TestCase):
    def test_mb(self):
        self.assertEqual(fontes._mb("1GiB"), 1024)
        self.assertAlmostEqual(fontes._mb("132.2MiB"), 132.2)
        self.assertAlmostEqual(fontes._mb("2048KiB"), 2)

    def test_docker_stats(self):
        r = fontes.parse_docker(DOCKER, 13603)
        self.assertEqual(r["n"], 3)
        self.assertEqual(r["mb"], 662)
        self.assertEqual(r["sem_teto"], ["studio"])

    def test_fatia(self):
        self.assertEqual(fontes.parse_fatia("MemoryCurrent=1048576\nMemoryMax=4294967296\n"), (1, 4096))
        self.assertEqual(fontes.parse_fatia("MemoryCurrent=[not set]\nMemoryMax=4294967296\n"), (None, 4096))


class TestTeto(unittest.TestCase):
    cfg = {"teto_memoria_mb": 8192, "fatia_testes": "testes.slice"}
    maq = {"total_mb": 13603, "livre_mb": 3819}

    def test_soma_tudo(self):
        t = fontes.montar_teto(self.cfg, 1500, (300, 4096), {"mb": 700, "n": 7, "sem_teto": []}, self.maq)
        self.assertEqual(t["usado_mb"], 2500)
        self.assertEqual(t["livre_mb"], 5692)
        self.assertEqual(t["pct"], 31)
        self.assertEqual([p["nome"] for p in t["partes"]],
                         ["Claude e agentes (este cgroup)", "Fatia de testes", "Contêineres"])
        self.assertEqual(t["faltando"], [])

    def test_parte_ilegivel_vira_null(self):
        t = fontes.montar_teto(self.cfg, 1500, None, None, self.maq)
        self.assertEqual(t["usado_mb"], 1500)
        self.assertIsNone(t["partes"][1]["mb"])
        self.assertIsNone(t["partes"][2]["mb"])
        self.assertEqual(t["faltando"], ["Fatia de testes", "Contêineres"])

    def test_livre_nunca_negativo(self):
        t = fontes.montar_teto(self.cfg, 9000, None, None, self.maq)
        self.assertEqual(t["livre_mb"], 0)


class TestSemFatia(unittest.TestCase):
    def test_sem_fatia_configurada_a_parte_some(self):
        r = fontes.montar_teto({"teto_memoria_mb": 8192}, 1000, None, None, {"total_mb": 16000, "livre_mb": 8000})
        self.assertEqual([p["nome"] for p in r["partes"]], ["Claude e agentes (este cgroup)", "Contêineres"])
        self.assertNotIn("Fatia de testes", r["faltando"])


class TestCache(unittest.TestCase):
    def test_nao_bloqueia_e_atualiza_em_fundo(self):
        fontes._docker_cache.update(t=0, dados=None, ocupado=False)
        def lento():
            time.sleep(0.3)
            return ["x"]
        t0 = time.time()
        self.assertIsNone(fontes.docker_em_cache(lento))
        self.assertLess(time.time() - t0, 0.1)
        time.sleep(0.5)
        self.assertEqual(fontes.docker_em_cache(lento), ["x"])


if __name__ == "__main__":
    unittest.main()
