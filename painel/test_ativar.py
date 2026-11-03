import os, tempfile, unittest
import ativar

BASE = {"projeto": "/x", "worktrees": "/y", "sessoes": "/z", "saidas": "/w", "sessao": "abc", "porta": 8791, "cache": "~/.cache"}


class Ativar(unittest.TestCase):
    def test_nome_do_diretorio_de_sessoes(self):
        self.assertEqual(ativar.nome_sessoes("/var/home/a.b/c_d"), "-var-home-a-b-c-d")

    def test_novo_config_troca_so_o_que_depende_do_projeto(self):
        with tempfile.TemporaryDirectory() as t:
            proj = os.path.join(t, "meu-proj")
            os.mkdir(proj)
            novo = ativar.novo_config(BASE, proj, home="/h", uid=1000)
            self.assertEqual(novo["projeto"], proj)
            self.assertEqual(novo["worktrees"], os.path.join(t, "wt"))
            self.assertEqual(novo["sessoes"], "/h/.claude/projects/" + ativar.nome_sessoes(proj))
            self.assertEqual(novo["saidas"], "/tmp/claude-1000/" + ativar.nome_sessoes(proj))
            self.assertIsNone(novo["sessao"])
            self.assertEqual(novo["porta"], 8791)
            self.assertEqual(BASE["projeto"], "/x")  # não muta a entrada

    def test_sem_mudanca_quando_ja_aponta(self):
        with tempfile.TemporaryDirectory() as t:
            proj = os.path.join(t, "p")
            os.mkdir(proj)
            a = ativar.novo_config(BASE, proj, home="/h", uid=1)
            self.assertEqual(ativar.novo_config(a, proj, home="/h", uid=1), a)

    def test_projeto_sem_wt_irma_nao_quebra(self):
        with tempfile.TemporaryDirectory() as t:
            proj = os.path.join(t, "p")
            os.mkdir(proj)
            self.assertFalse(os.path.exists(os.path.join(t, "wt")))
            novo = ativar.novo_config(BASE, proj, home="/h", uid=1)
            self.assertIsInstance(novo["worktrees"], str)  # fontes.py faz startswith

    def test_cwd_inexistente(self):
        with self.assertRaises(ValueError):
            ativar.projeto_de("/nao/existe/de/jeito/nenhum")

    def test_projeto_de_pasta_sem_git_e_a_propria_pasta(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(ativar.projeto_de(t), os.path.realpath(t))


if __name__ == "__main__":
    unittest.main()
