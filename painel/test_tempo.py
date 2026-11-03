import unittest

import tempo as t

AG = 1000.0
C = {"passo_s": 600, "n_passos": 20, "bat_s": 1800, "n_bat": 5, "tarefa_s": 7200, "n_tarefas": 4,
     "frentes": 3, "fila": ["wa", "wb"], "bateria_desde": None, "concluidas_s": {7: 5400}}


def tar(**k):
    base = {"id": 1, "estado": "andando", "worktree": None, "workflows": [], "wf_frac": None, "bateria_rodando": False}
    return {**base, **k}


class Fmt(unittest.TestCase):
    def test_arredonda(self):
        self.assertEqual(t.fmt(40 * 60), "~40 min")
        self.assertEqual(t.fmt(41 * 60), "~40 min")
        self.assertEqual(t.fmt(10), "~1 min")
        self.assertEqual(t.fmt(2 * 3600 + 8 * 60), "~2 h 10 min")
        self.assertEqual(t.fmt(3 * 3600), "~3 h")


class Estimar(unittest.TestCase):
    def test_workflow(self):
        r = t.estimar(tar(workflows=[{"rodando": True}], wf_frac=(3, 8)), C, AG)
        self.assertEqual(r["segundos"], 5 * 600)
        self.assertEqual(r["texto"], "~50 min")
        self.assertEqual(r["conclusao_em"], AG + 3000)
        self.assertIn("5 passo(s)", r["base"])

    def test_branch_pronta_na_fila(self):
        w = {"nome": "wb", "a_frente": 2, "na_dev": False}
        r = t.estimar(tar(worktree=w), C, AG)
        self.assertEqual(r["segundos"], 2 * 1800)  # posicao 1 -> (1+1) baterias

    def test_branch_pronta_fora_da_fila_vai_ao_fim(self):
        w = {"nome": "wz", "a_frente": 1, "na_dev": False}
        self.assertEqual(t.estimar(tar(worktree=w), C, AG)["segundos"], 3 * 1800)

    def test_fila_conta_a_bateria_rodando(self):
        w = {"nome": "wa", "a_frente": 1, "na_dev": False}
        c = {**C, "bateria_desde": AG - 600, "rodando": True}
        self.assertEqual(t.estimar(tar(worktree=w), c, AG)["segundos"], 1200 + 1800)

    def test_bateria_rodando_minimo_1_min(self):
        c = {**C, "bateria_desde": AG - 600}
        self.assertEqual(t.estimar(tar(bateria_rodando=True), c, AG)["segundos"], 1200)
        c = {**C, "bateria_desde": AG - 9000}
        self.assertEqual(t.estimar(tar(bateria_rodando=True), c, AG)["segundos"], 60)

    def test_fila_sem_comecar(self):
        r = t.estimar(tar(estado="fila"), C, AG)
        self.assertEqual(r["segundos"], 2400)  # 7200 / 3 frentes

    def test_concluida_real(self):
        r = t.estimar(tar(id=7, estado="concluida"), C, AG)
        self.assertEqual(r["texto"], "levou ~1 h 30 min")
        self.assertIsNone(r["conclusao_em"])
        self.assertIsNone(t.estimar(tar(id=8, estado="concluida"), C, AG))

    def test_sem_medida_nao_inventa(self):
        self.assertIsNone(t.estimar(tar(estado="fila"), {**C, "tarefa_s": None}, AG))
        self.assertIsNone(t.estimar(tar(estado="bloqueada"), C, AG))
        r = t.estimar(tar(workflows=[{"rodando": True}], wf_frac=(1, 2)), {**C, "passo_s": None}, AG)
        self.assertIsNone(r)


class Medidas(unittest.TestCase):
    def test_media(self):
        self.assertEqual(t.media([10, 20, 60]), 30)
        self.assertIsNone(t.media([]))

    def test_registro(self):
        txt = "- **Resultado:** VERDE (código de saída 0)\n- **Duração:** 3725 s\n"
        self.assertEqual(t.parse_registro(txt), 3725)
        self.assertEqual(t.parse_registro("- **Resultado:** VERDE\n- **Duração:** 57 s\n"), 57)
        self.assertIsNone(t.parse_registro("- **Resultado:** VERMELHO\n- **Duração:** 57 s\n"))


if __name__ == "__main__":
    unittest.main()
