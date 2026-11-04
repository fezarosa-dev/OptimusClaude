"""Testes do hook .githooks/commit-msg.

    python3 -I -m unittest discover -s scripts -p 'test_*.py'
"""
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / ".githooks" / "commit-msg"
_spec = importlib.util.spec_from_loader("commit_msg", importlib.machinery.SourceFileLoader("commit_msg", str(HOOK)))
commit_msg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(commit_msg)


class CommitMsg(unittest.TestCase):
    def test_aceita_o_padrao(self):
        for m in ("feat(relatorio): adiciona exportação em CSV", "fix: corrige fuso do total",
                  "docs(readme): explica o modo noturno\n\nPorque ninguém achava.\n", "feat(api)!: renomeia /pedidos",
                  "chore(registros): índice", "Merge branch 'feat/x' into dev", "fixup! feat: x",
                  "# comentário do git\nci: roda só no PR"):
            self.assertEqual(commit_msg.problemas(m), [], m)

    def test_recusa_fora_do_padrao(self):
        for m in ("adiciona csv", "Feat: x", "feat:sem espaço", "feature(x): y", "feat(X Y): z", "feat: termina.",
                  "feat: " + "a" * 70, "feat: x\ncorpo colado", ""):
            self.assertNotEqual(commit_msg.problemas(m), [], m)

    def test_recusa_autoria_de_ia(self):
        for corpo in ("Co-Authored-By: Claude <noreply@anthropic.com>", "🤖 Generated with Claude Code"):
            self.assertTrue(any("IA" in e for e in commit_msg.problemas(f"feat: x\n\n{corpo}\n")), corpo)
        self.assertEqual(commit_msg.problemas("feat: x\n\nCo-Authored-By: Maria <m@x.com>\n"), [])

    def test_script_sai_1_e_explica(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
            f.write("arrumei umas coisas\n")
        self.addCleanup(os.unlink, f.name)
        p = subprocess.run([sys.executable, str(HOOK), f.name], capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 1)
        self.assertIn("tipo(escopo): descrição", p.stderr)


if __name__ == "__main__":
    unittest.main()
