"""Testes do tarefa.py (brief de uma Tn) e do arquivar.py (arquivo morto do TASKS.md e do duvidas.md).

    python3 -I -m unittest discover -s scripts -p 'test_*.py'
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import arquivar  # noqa: E402
import tarefa  # noqa: E402

TASKS = """# Tarefas

Texto de abertura.

## Em andamento

### T7 · Total do mês com fuso

- **Fazer:** corrigir o total.
- **Estado:** aprovada.

### T8 · Botão de CSV

- **Estado:** em andamento.

## Feitas

### T1 · Ligar a bateria

- **Estado:** feita na `dev` (merge `abc`), no ar (PR #1).

### T2 · Tela de cadastro

- **Estado:** feita na `dev`.
"""

DUVIDAS = """# Dúvidas

Abertura.

## Decisões

### D-1. T7: fuso do total

- **Opções:** (a) do usuário; (b) UTC.

### D-2. T70: outra coisa

- **Opções:** (a); (b).

### D-3. T7: separador

- **Opções:** (a); (b).
- **Resposta (2026-11-01):** a.
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        (self.raiz / "TASKS.md").write_text(TASKS, encoding="utf-8")
        (self.raiz / "duvidas.md").write_text(DUVIDAS, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()


class Tarefa(Base):
    def test_devolve_so_a_secao_e_as_duvidas_abertas_dela(self):
        txt = tarefa.brief(self.raiz, "T7")
        self.assertIn("### T7 · Total do mês com fuso", txt)
        self.assertIn("corrigir o total", txt)
        self.assertNotIn("T8", txt)
        self.assertIn("D-1. T7: fuso do total", txt)
        self.assertNotIn("D-2", txt)  # T70 não é T7
        self.assertNotIn("D-3", txt)  # respondida

    def test_aceita_minuscula_e_tarefa_inexistente_da_none(self):
        self.assertIn("### T7", tarefa.brief(self.raiz, "t7"))
        self.assertIsNone(tarefa.brief(self.raiz, "T99"))

    def test_lista_as_abertas(self):
        self.assertEqual(tarefa.abertas(self.raiz), ["T7 · Total do mês com fuso · aprovada.",
                                                     "T8 · Botão de CSV · em andamento.",
                                                     "T2 · Tela de cadastro · feita na `dev`."])

    def test_script_sai_1_quando_nao_acha(self):
        p = subprocess.run([sys.executable, str(AQUI / "tarefa.py"), "T99"], cwd=self.raiz,
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 1)


class Arquivar(Base):
    def test_move_no_ar_e_respondidas_e_e_idempotente(self):
        movidas = arquivar.arquivar(self.raiz)
        self.assertEqual(movidas, {"tarefas": ["T1"], "duvidas": ["D-3"]})
        tasks = (self.raiz / "TASKS.md").read_text(encoding="utf-8")
        self.assertNotIn("T1 · Ligar", tasks)
        self.assertIn("T2 · Tela", tasks)
        self.assertIn("Texto de abertura.", tasks)
        self.assertIn("T1 · Ligar a bateria", (self.raiz / "docs" / "tarefas-feitas.md").read_text(encoding="utf-8"))
        duv = (self.raiz / "duvidas.md").read_text(encoding="utf-8")
        self.assertNotIn("D-3", duv)
        self.assertIn("D-1", duv)
        self.assertIn("D-3. T7: separador", (self.raiz / "docs" / "duvidas-resolvidas.md").read_text(encoding="utf-8"))
        self.assertEqual(arquivar.arquivar(self.raiz), {"tarefas": [], "duvidas": []})

    def test_sem_arquivos_nao_quebra(self):
        with tempfile.TemporaryDirectory() as vazio:
            self.assertEqual(arquivar.arquivar(Path(vazio)), {"tarefas": [], "duvidas": []})



class CercaDeCodigo(unittest.TestCase):
    """Linha '# comentário' dentro de bloco ``` não fecha a seção."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        (self.raiz / "TASKS.md").write_text(
            "# Tarefas\n\n## Feitas\n\n### T1 · Com código\n\n```bash\n# comentario\nmake x\n```\n\n"
            "Depois do bloco.\n- **Estado:** no ar (PR #1).\n\n### T2 · Outra\n\n- **Estado:** aprovada.\n",
            encoding="utf-8")
        (self.raiz / "duvidas.md").write_text("# Dúvidas\n\n### Sem id\n\n- **Resposta (2026-11-01):** a.\n",
                                              encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_brief_traz_a_secao_inteira(self):
        txt = tarefa.brief(self.raiz, "T1")
        self.assertIn("make x", txt)
        self.assertIn("Depois do bloco.", txt)

    def test_arquivar_move_a_secao_inteira_e_aguenta_duvida_sem_id(self):
        m = arquivar.arquivar(self.raiz)
        self.assertEqual(m["tarefas"], ["T1"])
        self.assertEqual(len(m["duvidas"]), 1)
        tasks = (self.raiz / "TASKS.md").read_text(encoding="utf-8")
        self.assertNotIn("make x", tasks)
        self.assertNotIn("```", tasks)
        self.assertIn("T2 · Outra", tasks)
        morto = (self.raiz / "docs" / "tarefas-feitas.md").read_text(encoding="utf-8")
        self.assertIn("make x", morto)
        self.assertIn("Depois do bloco.", morto)

if __name__ == "__main__":
    unittest.main()
