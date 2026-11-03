"""Escolha dos testes pelo que mudou (testar.py)."""
import tempfile
import unittest

import testar


def nomes(mudados):
    return {t.stem for t in testar.escolher(mudados)[0]}


TODOS = {t.stem for t in testar.AQUI.glob("test_*.py")}


class Escolher(unittest.TestCase):
    def test_modulo_roda_quem_importa_e_nao_o_resto(self):
        n = nomes(["tempo.py"])
        self.assertIn("test_tempo", n)
        self.assertNotIn("test_ordenar", n)

    def test_js_roda_quem_cita(self):
        self.assertIn("test_ordenar", nomes(["ordenar.js"]))

    def test_so_markdown_nao_roda_nada(self):
        self.assertEqual(nomes(["README.md", ".gitignore"]), set())

    def test_apagado_roda_tudo(self):
        self.assertEqual(nomes(["sumiu.py"]), TODOS)

    def test_sem_teste_ligado_roda_tudo(self):
        with tempfile.NamedTemporaryFile(dir=testar.AQUI, suffix=".txt") as f:
            self.assertEqual(nomes([f.name]), TODOS)


if __name__ == "__main__":
    unittest.main()
