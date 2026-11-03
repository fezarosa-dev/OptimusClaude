"""A % de trabalho feito anda junto com o trabalho: o anel conta o andamento das tarefas, e o workflow entre um passo e outro não some."""
import json
import os
import tempfile
import time
import unittest
from unittest import mock

import fontes
import servidor as s


class TestGeral(unittest.TestCase):
    def test_anel_conta_o_andamento_nao_so_as_concluidas(self):
        tar = [{"id": 1, "estado": "concluida", "percentual": 100}, {"id": 2, "estado": "andando", "percentual": 50}]
        with mock.patch.object(s.fontes, "tarefas", return_value=tar):
            g = s.montar()["geral"]
        self.assertEqual(g["percentual"], 75)
        self.assertEqual(g["contagem"], {"concluida": 1, "andando": 1})

    def test_sem_tarefas_e_zero(self):
        with mock.patch.object(s.fontes, "tarefas", return_value=[]):
            self.assertEqual(s.montar()["geral"]["percentual"], 0)


def _journal(sd, wid, linhas, idade=0):
    d = os.path.join(sd, "subagents", "workflows", wid)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "journal.jsonl")
    with open(p, "w") as f:
        f.write("\n".join(json.dumps(l) for l in linhas) + "\n")
    t = time.time() - idade
    os.utime(p, (t, t))


DOIS_PRONTOS = [{"agentId": "a1", "type": "started", "label": "T200 implementar", "phase": "fazer"},
                {"agentId": "a1", "type": "result", "result": {"status": "ok"}},
                {"agentId": "a2", "type": "started", "label": "T200 revisar", "phase": "revisar"},
                {"agentId": "a2", "type": "result", "result": {"status": "ok"}}]


class TestWorkflowEntrePassos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sd = os.path.join(self.tmp.name, "sessao")
        self.proj = os.path.join(self.tmp.name, "proj")
        os.makedirs(self.proj)
        with open(os.path.join(self.proj, "TASKS.md"), "w") as f:
            f.write("### T200 · Nova\n- **Estado:** em andamento.\n")
        self.cfg = {"projeto": self.proj, "leva_a_partir_de": 1, "ativo_segundos": 120}

    def _tarefa(self):
        _, wfs = fontes.agentes_e_workflows(self.cfg, self.sd)
        bat = {"rodando": None, "fila": []}
        return fontes.tarefas(self.cfg, [], wfs, bat)[0]

    def test_sem_agente_vivo_mas_sem_fim_a_fracao_continua(self):
        # os dois passos terminaram e o próximo ainda não começou: o workflow segue, a % não volta para 40
        _journal(self.sd, "wf_1", DOIS_PRONTOS)
        t = self._tarefa()
        self.assertEqual(t["wf_frac"], (2, 2))
        self.assertEqual(t["percentual"], 95)

    def test_workflow_terminado_nao_conta(self):
        _journal(self.sd, "wf_1", DOIS_PRONTOS, idade=60)
        os.makedirs(os.path.join(self.sd, "workflows"))
        with open(os.path.join(self.sd, "workflows", "wf_1.json"), "w") as f:
            json.dump({"status": "completed"}, f)
        self.assertIsNone(self._tarefa()["wf_frac"])

    def test_workflow_parado_ha_horas_nao_conta(self):
        _journal(self.sd, "wf_1", DOIS_PRONTOS, idade=3 * 3600)
        self.assertIsNone(self._tarefa()["wf_frac"])


if __name__ == "__main__":
    unittest.main()
