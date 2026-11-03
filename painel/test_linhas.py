"""Quadro 'Linhas desde a main': classificação por categoria e git de verdade num repositório temporário."""
import os
import shutil
import subprocess
import tempfile
import unittest

import linhas as L

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, check=True, capture_output=True, text=True).stdout


def escrever(raiz, caminho, linhas_n, binario=False, versao=0):
    p = os.path.join(raiz, caminho)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if binario:
        with open(p, "wb") as f:
            f.write(b"\x00\x01\x02" * 10)
    else:
        with open(p, "w") as f:
            f.write("".join(f"{caminho} {versao} l{i}\n" for i in range(linhas_n)))


class Categoria(unittest.TestCase):
    def test_cada_categoria(self):
        casos = {
            "supabase/migrations/001_x.sql": "sql", "supabase/tests/a.sql": "sql",
            "comum/a.py": "py", "agentes/x/testes/test_a.py": "py_teste", "agentes/x/test_b.py": "py_teste",
            "painel/spa/src/a.ts": "ts", "painel/spa/src/a.tsx": "ts", "b.mjs": "ts", "c.js": "ts",
            "painel/spa/src/a.test.ts": "ts_teste", "a.spec.tsx": "ts_teste", "painel/spa/e2e/rotas.ts": "ts_teste",
            "scripts/a.sh": "shell", "scripts/a.ps1": "shell", "scripts/a.psm1": "shell",
            "painel/package.json": "config", "x.yml": "config", "a.css": "config", "Dockerfile": "config",
            "painel/spa/package-lock.json": "lock", "uv.lock": "lock", "agentes/x/constraints.txt": "lock",
            "constraints-dev.txt": "lock",
            "docs/a.md": "md", "a fazeres.md": "md",
        }
        for caminho, esperado in casos.items():
            self.assertEqual(L.categoria(caminho), esperado, caminho)

    def test_registros_vence_a_extensao(self):
        for c in ("registros/a.md", "registros/x/bateria.log", "registros/t.py", "registros/test_a.py", "registros/p.sql", "registros/package-lock.json"):
            self.assertEqual(L.categoria(c), "registros", c)

    def test_lockfile_vence_config(self):
        self.assertEqual(L.categoria("package-lock.json"), "lock")

    def test_renomeado_usa_o_destino(self):
        self.assertEqual(L.categoria("a/{x.md => y.py}"), "py")
        self.assertEqual(L.categoria("a.md => b/c.sql"), "sql")


class Somar(unittest.TestCase):
    def test_nome_com_espaco_e_binario(self):
        txt = "3\t1\ta fazeres.md\n-\t-\timg.png\n5\t0\tx/test_a.py\n2\t2\tx/b.py\n"
        r = L.somar(txt)
        self.assertEqual(r["md"], (3, 1))
        self.assertEqual(r["py_teste"], (5, 0))
        self.assertEqual(r["py"], (2, 2))
        self.assertNotIn("config", r)  # binário ignorado, não vira config

    def test_codigo_e_testes_soma_so_adicionadas_das_quatro(self):
        r = {"sql": (10, 1), "py": (20, 2), "py_teste": (30, 3), "ts": (1, 9), "ts_teste": (2, 9), "shell": (4, 4),
             "md": (1000, 0), "config": (500, 0), "lock": (700, 0), "registros": (900, 0)}
        self.assertEqual(L.codigo_e_testes(r), 10 + 20 + 30 + 1 + 2 + 4)


class Shortstat(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(L.shortstat(" 3 files changed, 10 insertions(+), 2 deletions(-)\n"), (10, 2))
        self.assertEqual(L.shortstat(" 1 file changed, 4 insertions(+)\n"), (4, 0))
        self.assertEqual(L.shortstat(" 1 file changed, 3 deletions(-)\n"), (0, 3))
        self.assertEqual(L.shortstat(""), (0, 0))


class ComGit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj = os.path.join(self.tmp, "proj")
        self.wt = os.path.join(self.tmp, "wt")
        os.makedirs(self.proj)
        git(self.proj, "init", "-q", "-b", "main")
        escrever(self.proj, "a.py", 4)
        escrever(self.proj, "velho.md", 3)
        git(self.proj, "add", "-A")
        git(self.proj, "commit", "-qm", "base")
        git(self.proj, "update-ref", "refs/remotes/origin/main", "main")
        git(self.proj, "checkout", "-qb", "dev")
        escrever(self.proj, "a.py", 6, versao=1)                       # +6 -4 em py (reescrito)
        escrever(self.proj, "testes/test_a.py", 7)           # +7 py_teste
        escrever(self.proj, "m/001.sql", 5)                  # +5 sql
        escrever(self.proj, "a fazeres.md", 2)               # +2 md (nome com espaço)
        escrever(self.proj, "registros/r.md", 11)            # +11 registros
        escrever(self.proj, "package-lock.json", 8)          # +8 lock
        escrever(self.proj, "img.png", 0, binario=True)      # binário
        os.remove(os.path.join(self.proj, "velho.md"))       # -3 md, removido
        git(self.proj, "add", "-A")
        git(self.proj, "commit", "-qm", "dev")
        self.cfg = {"projeto": self.proj, "worktrees": self.wt}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_totais_por_categoria(self):
        q = L.coletar(self.cfg)
        por = {c["chave"]: (c["adicionadas"], c["removidas"]) for c in q["categorias"]}
        self.assertEqual(por["py"], (6, 4))
        self.assertEqual(por["py_teste"], (7, 0))
        self.assertEqual(por["sql"], (5, 0))
        self.assertEqual(por["md"], (2, 3))
        self.assertEqual(por["registros"], (11, 0))
        self.assertEqual(por["lock"], (8, 0))
        self.assertEqual(q["total"], {"adicionadas": 39, "removidas": 7})
        self.assertEqual(q["codigo_e_testes"], 6 + 7 + 5)
        self.assertEqual([c["chave"] for c in q["categorias"]][:3], ["sql", "py", "py_teste"])
        self.assertEqual(q["avisos"], [])

    def test_contagem_de_arquivos(self):
        q = L.coletar(self.cfg)
        # adicionados: testes/test_a.py, m/001.sql, a fazeres.md, registros/r.md, package-lock.json, img.png; modificado: a.py; removido: velho.md
        self.assertEqual(q["arquivos"], {"adicionados": 6, "modificados": 1, "removidos": 1})

    def test_worktree_a_frente_da_dev_e_nao_commitado(self):
        git(self.proj, "worktree", "add", "-q", "-b", "feat/x", os.path.join(self.wt, "x"), "dev")
        git(self.proj, "worktree", "add", "-q", "-b", "feat/igual", os.path.join(self.wt, "igual"), "dev")
        x = os.path.join(self.wt, "x")
        escrever(x, "n.py", 9)
        git(x, "add", "-A")
        git(x, "commit", "-qm", "x")
        escrever(x, "a.py", 1, versao=2)  # 6 linhas viram 1 (+1 -6) ainda não commitado
        q = L.coletar(self.cfg)
        self.assertEqual(q["worktrees"], [{"ramo": "feat/x", "a_frente": {"adicionadas": 9, "removidas": 0},
                                           "por_commitar": {"adicionadas": 1, "removidas": 6}}])

    def test_nao_mexe_no_indice(self):
        escrever(self.proj, "novo.py", 3)  # não rastreado
        antes = git(self.proj, "status", "--porcelain")
        L.coletar(self.cfg)
        self.assertEqual(git(self.proj, "status", "--porcelain"), antes)

    def test_erro_do_git_vira_aviso(self):
        q = L.coletar({"projeto": os.path.join(self.tmp, "nao-existe"), "worktrees": self.wt})
        self.assertTrue(q["avisos"])
        self.assertEqual(q["total"], {"adicionadas": 0, "removidas": 0})

    def test_sem_origin_main_vira_aviso(self):
        git(self.proj, "update-ref", "-d", "refs/remotes/origin/main")
        q = L.coletar(self.cfg)
        self.assertTrue(any("origin/main" in x for x in q["avisos"]))

    def test_ramo_passa_por_mascarar(self):
        git(self.proj, "worktree", "add", "-q", "-b", "feat/fulano@exemplo.com", os.path.join(self.wt, "m"), "dev")
        escrever(os.path.join(self.wt, "m"), "n.py", 2)
        git(os.path.join(self.wt, "m"), "add", "-A")
        git(os.path.join(self.wt, "m"), "commit", "-qm", "m")
        q = L.coletar(self.cfg)
        self.assertEqual(len(q["worktrees"]), 1)
        self.assertNotIn("fulano@exemplo.com", q["worktrees"][0]["ramo"])


if __name__ == "__main__":
    unittest.main()
