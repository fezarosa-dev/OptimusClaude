"""Testes dos scripts do projeto: o mapa do que testar, a bateria (só a decisão) e os registros de garantia.

    python3 -I -m unittest discover -s scripts -p 'test_*.py'

Só biblioteca padrão. A bateria entra com SO_DECIDIR=1, num repositório git temporário (não roda teste de verdade).
"""
import datetime
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
sys.path.insert(0, str(AQUI / "registros"))

import indice  # noqa: E402
import o_que_testar  # noqa: E402
import salvar_revisao  # noqa: E402
import sensivel  # noqa: E402

# JWT de exemplo, montado em partes para o próprio arquivo de teste não parecer segredo ao gitleaks
JWT = "eyJhbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiIxMjM0NTY3ODkwIn0" + "." + "abcdefghijklmnopqrstuv"


CMD_BATERIA = [sys.executable, "scripts/testar_como_o_ci.py"]


class OQueTestar(unittest.TestCase):
    def test_sem_mudanca_roda_so_o_que_roda_sempre(self):
        self.assertEqual(o_que_testar.decidir([]), sorted(o_que_testar.SEMPRE))

    def test_markdown_nao_liga_nada_alem_do_sempre(self):
        self.assertEqual(o_que_testar.decidir(["docs/qualquer.md", "README.md"]), sorted(o_que_testar.SEMPRE))

    def test_caminho_desconhecido_roda_tudo(self):
        self.assertEqual(o_que_testar.decidir(["algo/que/o/mapa/nao/conhece.xyz"]), sorted(o_que_testar.VERIFICACOES))

    def test_workflow_do_ci_liga_o_actionlint(self):
        self.assertIn("actions", o_que_testar.decidir([".github/workflows/testes.yml"]))

    def test_mostrar_devolve_requer_e_comando_separados_por_tab(self):
        requer, comando = o_que_testar.mostrar("shell").split("\t")
        self.assertEqual(requer, "shellcheck xargs")
        self.assertIn("shellcheck", comando)

    def test_todo_passo_do_mapa_existe_nas_verificacoes(self):
        for _, passos in o_que_testar.MAPA:
            self.assertLessEqual(set(passos), set(o_que_testar.VERIFICACOES))
        self.assertLessEqual(set(o_que_testar.SEMPRE), set(o_que_testar.VERIFICACOES))


class Sensivel(unittest.TestCase):
    def test_acha_jwt_sem_devolver_o_valor(self):
        achados = sensivel.achar(f"linha limpa\ntoken {JWT}\n")
        self.assertEqual(achados, [(2, "JWT")])

    def test_cpf_valido_e_dado_pessoal_e_o_invalido_nao(self):
        self.assertEqual(sensivel.achar("cpf 529.982.247-25"), [(1, "CPF")])
        self.assertEqual(sensivel.achar("cpf 529.982.247-24"), [])

    def test_email_de_dominio_de_teste_passa(self):
        self.assertEqual(sensivel.achar("fulano@example.com"), [])
        self.assertEqual(sensivel.achar("fulano@empresa.com.br"), [(1, "e-mail")])

    def test_chave_privada(self):
        self.assertEqual(sensivel.achar("-----BEGIN " + "PRIVATE KEY-----"), [(1, "chave privada")])


class Registros(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.pasta)

    def test_indice_gera_e_confere(self):
        (self.pasta / "baterias").mkdir()
        (self.pasta / "baterias" / "a.md").write_text("x", encoding="utf-8")
        indice.escrever(self.pasta)
        self.assertTrue(indice.conferir(self.pasta))
        (self.pasta / "baterias" / "a.md").write_text("mudou", encoding="utf-8")
        self.assertFalse(indice.conferir(self.pasta))

    def test_salvar_revisao_recusa_segredo(self):
        relatorio = self.pasta / "rel.md"
        relatorio.write_text(f"achado com {JWT}\n", encoding="utf-8")
        with self.assertRaises(ValueError) as erro:
            salvar_revisao.salvar("security-review", relatorio, pasta=self.pasta, commit="abc")
        self.assertNotIn(JWT, str(erro.exception))

    def test_salvar_revisao_profunda_vira_secoes(self):
        relatorio = self.pasta / "rel.json"
        relatorio.write_text(json.dumps({"base": "main", "resumo": "ok", "confirmados": [
            {"arquivo": "src/a.py", "linha": 3, "gravidade": "alta", "resumo": "falta conferir acesso"}],
            "nao_verificados": [], "derrubados": []}), encoding="utf-8")
        destino = salvar_revisao.salvar("revisao-profunda", relatorio, pasta=self.pasta,
                                        hoje=datetime.date(2030, 1, 2), commit="abc")
        texto = destino.read_text(encoding="utf-8")
        self.assertEqual(destino.name, "2030-01-02-revisao-profunda.md")
        self.assertIn("## Confirmados (1)", texto)
        self.assertIn("src/a.py:3", texto)


class Bateria(unittest.TestCase):
    """A bateria pega o diff contra a base, o que não foi commitado e o arquivo novo, e passa ao mapa."""

    def _git(self, *args):
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
        subprocess.run(["git", "-c", "init.defaultBranch=dev", *args], cwd=self.repo, check=True,
                       capture_output=True, env=env)

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)
        shutil.copytree(AQUI, self.repo / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        self._git("init", "-q")
        self._git("add", ".")
        self._git("commit", "-qm", "base")
        self._git("checkout", "-qb", "feat/x")

    def _falsificar(self, sempre, verificacoes):
        """Troca o mapa da cópia por verificações de mentira, para a bateria rodar de verdade e depressa."""
        arq = self.repo / "scripts" / "o_que_testar.py"
        texto = arq.read_text(encoding="utf-8")
        texto = texto.replace('SEMPRE = ["segredos", "scripts"]', f"SEMPRE = {sempre!r}")
        texto = texto.replace("def _passos", f"MAPA.insert(0, ('', []))\nVERIFICACOES.clear()\nVERIFICACOES.update({verificacoes!r})\n\n\ndef _passos", 1)
        arq.write_text(texto, encoding="utf-8")
        self._git("commit", "-qam", "mapa falso")

    def _rodar(self, *args, **env):
        base = {k: v for k, v in os.environ.items() if k not in ("EXIGIR_TUDO", "ARQUIVOS", "SO_DECIDIR", "REGISTRO")}
        self.fora = self.repo / "fora"
        return subprocess.run(CMD_BATERIA + list(args), cwd=self.repo, capture_output=True, text=True,
                              env={**base, "REGISTROS_FORA": str(self.fora), **env})

    OK = (["python3"], "python3 -c \"print('oi')\"")
    RUIM = (["python3"], "python3 -c \"import sys; sys.exit(3)\"")
    FALTA = (["programa-inexistente-xyz"], "programa-inexistente-xyz")

    def test_rodada_verde_sai_0_e_grava_resumo_com_sha256(self):
        self._falsificar(["ok"], {"ok": self.OK})
        saida = self._rodar("dev")
        self.assertEqual(saida.returncode, 0, saida.stdout + saida.stderr)
        self.assertIn("== ok: python3 -c", saida.stdout)
        self.assertIn("oi\n", saida.stdout)
        self.assertIn("Resumo:", saida.stdout)
        self.assertTrue(saida.stdout.rstrip().endswith("VERDE."))
        resumos = list((self.repo / "registros" / "baterias").glob("*.md"))
        self.assertEqual(len(resumos), 1)
        texto = resumos[0].read_text(encoding="utf-8")
        self.assertIn("- **Resultado:** VERDE", texto)
        self.assertIn("| ok | OK |", texto)
        self.assertIn("- **Mudança não commitada:** sim", texto)  # registros/ novo não conta, mas o fora/ conta
        logs = list(self.fora.rglob("*.log.gz"))
        self.assertEqual(len(logs), 1)
        import gzip, hashlib
        self.assertIn(hashlib.sha256(logs[0].read_bytes()).hexdigest(), texto)
        self.assertIn("oi", gzip.decompress(logs[0].read_bytes()).decode())

    def test_falha_e_falta_de_programa_reprovam_e_marcam(self):
        self._falsificar(["ok", "ruim", "falta"], {"ok": self.OK, "ruim": self.RUIM, "falta": self.FALTA})
        saida = self._rodar("dev")
        self.assertEqual(saida.returncode, 1, saida.stdout)
        self.assertIn("== falta: PULADO, falta: programa-inexistente-xyz", saida.stdout)
        self.assertIn("VERMELHA: não junte.", saida.stdout)
        texto = next((self.repo / "registros" / "baterias").glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("- **Resultado:** VERMELHA", texto)
        for linha in ("| ok | OK |", "| ruim | FALHOU |", "| falta | PULADO (falta: programa-inexistente-xyz) |"):
            self.assertIn(linha, texto)

    def test_pulado_so_reprova_com_exigir_tudo(self):
        self._falsificar(["ok", "falta"], {"ok": self.OK, "falta": self.FALTA})
        self.assertEqual(self._rodar("dev", REGISTRO="0").returncode, 0)
        self.assertEqual(self._rodar("dev", REGISTRO="0", EXIGIR_TUDO="1").returncode, 1)

    def test_registro_zero_nao_grava_nada(self):
        self._falsificar(["ok"], {"ok": self.OK})
        self.assertEqual(self._rodar("dev", REGISTRO="0").returncode, 0)
        self.assertFalse((self.repo / "registros").exists())
        self.assertFalse(self.fora.exists())

    def test_base_inexistente_sai_2(self):
        saida = self._rodar("nao-existe", REGISTRO="0")
        self.assertEqual(saida.returncode, 2)
        self.assertIn("base 'nao-existe' não existe", saida.stderr)

    def test_arquivos_usa_a_lista_dada(self):
        (self.repo / "lista.txt").write_text("notas.md\n\n", encoding="utf-8")
        saida = self._rodar("dev", ARQUIVOS=str(self.repo / "lista.txt"), SO_DECIDIR="1")
        self.assertIn("Arquivos (1):\n  notas.md\n", saida.stdout)

    def _decidir(self):
        # a bateria de fora (EXIGIR_TUDO, ARQUIVOS) não pode vazar para a de dentro
        env = {k: v for k, v in os.environ.items() if k not in ("EXIGIR_TUDO", "ARQUIVOS")}
        saida = subprocess.run(CMD_BATERIA + ["dev"], cwd=self.repo, capture_output=True,
                               text=True, env={**env, "SO_DECIDIR": "1", "REGISTRO": "0"})
        self.assertEqual(saida.returncode, 0, saida.stderr)
        return saida.stdout

    def test_so_markdown_novo_roda_so_o_sempre(self):
        (self.repo / "notas.md").write_text("x", encoding="utf-8")
        saida = self._decidir()
        self.assertIn("notas.md", saida)
        self.assertNotIn("shell", saida.split("Passos:")[1])

    def test_script_mudado_e_nao_commitado_liga_o_shellcheck(self):
        with open(self.repo / "scripts" / "testar_como_o_ci.py", "a", encoding="utf-8") as f:
            f.write("\n# mudança\n")
        self.assertIn("shell", self._decidir().split("Passos:")[1])


if __name__ == "__main__":
    unittest.main()
