"""Qualquer projeto: o que o painel lê vem do config, e o quadro sem fonte fica vazio, sem erro."""
import os
import tempfile
import unittest

import ativar
import fontes


class TestSemArquivos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = {"projeto": self.tmp.name, "leva_a_partir_de": 1}

    def test_projeto_sem_nada_fica_vazio(self):
        self.assertEqual(fontes.tarefas(self.cfg, [], [], {"rodando": None, "fila": []}), [])
        self.assertEqual(fontes.duvidas(self.cfg), {"abertas": [], "avisos": []})
        self.assertEqual(fontes.publicacao(self.cfg)["itens"], 0)
        self.assertEqual(fontes.perguntas(self.cfg, os.path.join(self.tmp.name, "nao-existe.json")), ([], []))

    def test_arquivos_e_secao_pelo_config(self):
        os.makedirs(os.path.join(self.tmp.name, "planos"))
        with open(os.path.join(self.tmp.name, "planos", "fila.md"), "w") as f:
            f.write("### T3 · Algo\n- **Estado:** em andamento.\n")
        with open(os.path.join(self.tmp.name, "abertas.md"), "w") as f:
            f.write("## Recados\n- olhar o deploy\n\n## Abertas\n### D-1. Qual?\n- Situação: x\n")
        cfg = dict(self.cfg, arquivo_tarefas="planos/fila.md", arquivo_duvidas="abertas.md", secao_avisos="## Recados")
        self.assertEqual([t["id"] for t in fontes.tarefas(cfg, [], [], {"rodando": None, "fila": []})], [3])
        d = fontes.duvidas(cfg)
        self.assertEqual(([x["id"] for x in d["abertas"]], d["avisos"]), (["D-1"], ["olhar o deploy"]))


class TestBateriasPeloConfig(unittest.TestCase):
    def test_padrao_de_log_configurado(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "ci-minha-branch.txt"), "w") as f:
                f.write("::: lint\n")
            cfg = {"cache": d, "bateria_logs": "ci-*.txt", "saidas": d, "ativo_segundos": 120, "worktrees": ""}
            b = fontes.baterias(cfg, [])
        self.assertEqual([l["wt"] for l in b["logs"]], ["minha-branch"])


class TestAtivarWorktrees(unittest.TestCase):
    def test_pasta_dos_worktrees_relativa_ao_projeto(self):
        c = ativar.novo_config({"worktrees_relativo": ".worktrees"}, "/p/proj", home="/h", uid=1)
        self.assertEqual(c["worktrees"], "/p/proj/.worktrees")
        self.assertEqual(ativar.novo_config({}, "/p/proj", home="/h", uid=1)["worktrees"], "/p/wt")


if __name__ == "__main__":
    unittest.main()
