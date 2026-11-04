"""Testes do orcamento_contexto.py. Rodar: python3 -m unittest discover -s claude/scripts"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import orcamento_contexto as oc  # noqa: E402


class Orcamento(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name, "home")
        self.proj = Path(self.tmp.name, "proj")
        (self.home / ".claude" / "skills" / "a").mkdir(parents=True)
        self.proj.mkdir()
        (self.home / ".claude" / "CLAUDE.md").write_text("@RTK.md\n# Regras\n" + "x" * 350, encoding="utf-8")
        (self.home / ".claude" / "RTK.md").write_text("r" * 70, encoding="utf-8")
        (self.home / ".claude" / "skills" / "a" / "SKILL.md").write_text(
            "---\nname: a\ndescription: faz a coisa\n---\n" + "corpo que não entra " * 100, encoding="utf-8")
        (self.proj / "CLAUDE.md").write_text("@docs/x.md\n" + "p" * 35, encoding="utf-8")
        (self.proj / "docs").mkdir()
        (self.proj / "docs" / "x.md").write_text("@../CLAUDE.md\n" + "d" * 35, encoding="utf-8")  # ciclo
        mem = self.home / ".claude" / "projects" / str(self.proj).replace(os.sep, "-") / "memory"
        mem.mkdir(parents=True)
        (mem / "MEMORY.md").write_text("m" * 35, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_conta_cada_fonte_segue_imports_sem_loop_e_so_a_descricao_da_skill(self):
        itens = dict(oc.medir(self.home, self.proj))
        nomes = set(itens)
        self.assertTrue(any(n.endswith("home/.claude/CLAUDE.md") for n in nomes), nomes)
        self.assertTrue(any(n.endswith("RTK.md") for n in nomes))
        self.assertTrue(any(n.endswith("proj/CLAUDE.md") for n in nomes))
        self.assertTrue(any(n.endswith("docs/x.md") for n in nomes))
        self.assertTrue(any(n.endswith("MEMORY.md") for n in nomes))
        skills = [v for n, v in itens.items() if n.startswith("skills")]
        self.assertEqual(len(skills), 1)
        self.assertLess(skills[0], 20)  # só nome + descrição, não o corpo
        self.assertEqual(len([n for n in nomes if n.endswith("proj/CLAUDE.md")]), 1)

    def test_relatorio_avisa_acima_do_limite(self):
        itens = oc.medir(self.home, self.proj)
        self.assertNotIn("ACIMA", oc.relatorio(itens, limite=10_000))
        self.assertIn("ACIMA", oc.relatorio(itens, limite=10))


if __name__ == "__main__":
    unittest.main()
