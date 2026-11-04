"""Testes do modo noturno: a guarda (o que nega) e o laço do noite.py com um `claude` falso no PATH.

    python3 -I -m unittest discover -s scripts -p 'test_*.py'
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import noite_guarda  # noqa: E402


def bash(cmd):
    return noite_guarda.decidir({"tool_name": "Bash", "tool_input": {"command": cmd}})


class Guarda(unittest.TestCase):
    def test_nega_o_que_sai_da_maquina_ou_toca_a_main(self):
        for cmd in ("git push", "git push origin dev", "rtk git push -u origin feat/x", "gh pr merge 3 --merge",
                    "gh pr create --fill", "git checkout main", "git switch master", "git merge origin/main",
                    "git rebase main", "git reset --hard HEAD~1", "git branch -D feat/x", "cd x && git push"):
            self.assertIsNotNone(bash(cmd), cmd)

    def test_deixa_o_trabalho_normal(self):
        for cmd in ("git status", "git switch dev", "git merge --no-ff feat/t3", "git worktree add ../wt -b feat/t3",
                    "git commit -m 'feat: x'", "scripts/testar_como_o_ci.py", "git log --oneline main..dev",
                    "pytest -q", "git branch -d feat/t3"):
            self.assertIsNone(bash(cmd), cmd)

    def test_entrada_ilegivel_e_negada(self):
        p = subprocess.run([sys.executable, str(AQUI / "noite_guarda.py")], input="não é json",
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "o claude falso é um script bash")
class Laco(unittest.TestCase):
    """noite.py com um claude falso que devolve respostas prontas, uma por chamada."""

    def rodar(self, respostas):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo, bin_ = Path(tmp.name, "repo"), Path(tmp.name, "bin")
        (repo / "scripts").mkdir(parents=True)
        bin_.mkdir()
        for nome in ("noite.py", "noite_guarda.py"):
            (repo / "scripts" / nome).write_text((AQUI / nome).read_text())
        (repo / "TASKS.md").write_text("# Tarefas\n")
        fila = Path(tmp.name, "fila")
        fila.write_text("\n".join(respostas) + "\n")
        falso = bin_ / "claude"
        falso.write_text(f'#!/usr/bin/env bash\nl="$(head -1 {fila})"; sed -i 1d {fila}\n'
                         'case "$l" in ERRO) exit 1;; esac\necho "trabalhando..."; echo "$l"\n')
        falso.chmod(0o755)
        g = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True)
        g("init", "-q", "-b", "dev")
        g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "início")
        g("add", "-A")
        g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
        env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "NTFY_TOPICO": ""}
        p = subprocess.run([sys.executable, "scripts/noite.py"], cwd=repo, capture_output=True, text=True, env=env,
                           timeout=30)
        return p, (fila.read_text().strip())

    def test_roda_ate_a_fila_esvaziar_sem_limite_de_tarefas(self):
        respostas = [f"NOITE_TAREFA T{i} feita ok" for i in range(1, 13)] + ["NOITE_FIM"]
        p, sobra = self.rodar(respostas)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("12 feita(s)", p.stdout)
        self.assertIn("fila vazia", p.stdout)
        self.assertEqual(sobra, "")

    def test_travada_conta_e_segue(self):
        p, _ = self.rodar(["NOITE_TAREFA T1 travada precisa decidir", "NOITE_TAREFA T2 feita ok", "NOITE_FIM"])
        self.assertIn("1 feita(s) T2", p.stdout)
        self.assertIn("1 travada(s) T1", p.stdout)

    def test_mesma_tarefa_duas_vezes_para(self):
        p, sobra = self.rodar(["NOITE_TAREFA T1 travada x", "NOITE_TAREFA T1 travada x", "NOITE_FIM"])
        self.assertIn("T1 voltou duas vezes seguidas", p.stdout)
        self.assertEqual(sobra, "NOITE_FIM")

    def test_tres_falhas_seguidas_param(self):
        p, sobra = self.rodar(["ERRO", "ERRO", "ERRO", "NOITE_FIM"])
        self.assertIn("3 falhas seguidas", p.stdout)
        self.assertEqual(sobra, "NOITE_FIM")


if __name__ == "__main__":
    unittest.main()
