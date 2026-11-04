"""Testes dos hooks do método. Rodar: python3 -m unittest discover -s claude/hooks"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import contexto_baixo  # noqa: E402
import ler_grande  # noqa: E402
import so_subagente_edita  # noqa: E402


def rodar(script, entrada, env=None):
    p = subprocess.run([sys.executable, os.path.join(AQUI, script)], input=entrada, capture_output=True, text=True,
                       env={**os.environ, **(env or {})}, timeout=10)
    return p.returncode, p.stdout


class LerGrande(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.grande = os.path.join(self.tmp.name, "a.py")
        with open(self.grande, "w") as f:
            f.write("x = 1\n" * 7000)  # ~42 KB
        self.pequeno = os.path.join(self.tmp.name, "b.py")
        with open(self.pequeno, "w") as f:
            f.write("x = 1\n")
        self.doc = os.path.join(self.tmp.name, "c.md")
        with open(self.doc, "w") as f:
            f.write("texto\n" * 7000)

    def tearDown(self):
        self.tmp.cleanup()

    def e(self, caminho, **extra):
        return {"tool_name": "Read", "tool_input": {"file_path": caminho, **extra}}

    def test_nega_codigo_grande_inteiro(self):
        self.assertIn("Serena", ler_grande.decidir(self.e(self.grande)))

    def test_passa_com_offset_ou_limit(self):
        self.assertIsNone(ler_grande.decidir(self.e(self.grande, offset=10)))
        self.assertIsNone(ler_grande.decidir(self.e(self.grande, limit=50)))

    def test_passa_pequeno_documento_e_inexistente(self):
        self.assertIsNone(ler_grande.decidir(self.e(self.pequeno)))
        self.assertIsNone(ler_grande.decidir(self.e(self.doc)))
        self.assertIsNone(ler_grande.decidir(self.e(os.path.join(self.tmp.name, "nao.py"))))

    def test_desligado_por_variavel(self):
        os.environ["OPTIMUS_LER_TUDO"] = "1"
        try:
            self.assertIsNone(ler_grande.decidir(self.e(self.grande)))
        finally:
            del os.environ["OPTIMUS_LER_TUDO"]

    def test_saida_do_script(self):
        cod, out = rodar("ler_grande.py", json.dumps(self.e(self.grande)))
        self.assertEqual(cod, 0)
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(rodar("ler_grande.py", "isto não é json"), (0, ""))


class SoSubagenteEdita(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = os.path.join(self.tmp.name, "proj")
        os.makedirs(os.path.join(self.proj, "src"))
        os.makedirs(os.path.join(self.proj, "registros"))
        open(os.path.join(self.proj, "TASKS.md"), "w").close()
        self.fora = os.path.join(self.tmp.name, "outro", "x.py")

    def tearDown(self):
        self.tmp.cleanup()

    def e(self, caminho, ferramenta="Edit", **extra):
        return {"tool_name": ferramenta, "tool_input": {"file_path": caminho}, **extra}

    def test_nega_principal_editando_codigo(self):
        self.assertIn("subagente", so_subagente_edita.decidir(self.e(os.path.join(self.proj, "src", "a.py"))))
        self.assertIsNotNone(so_subagente_edita.decidir(self.e(os.path.join(self.proj, "src", "a.py"), "Write")))

    def test_subagente_passa(self):
        self.assertIsNone(so_subagente_edita.decidir(self.e(os.path.join(self.proj, "src", "a.py"), agent_id="x")))

    def test_arquivos_de_estado_passam(self):
        for rel in ("TASKS.md", "duvidas.md", "src/LEIA.md", "registros/correcoes.txt"):
            self.assertIsNone(so_subagente_edita.decidir(self.e(os.path.join(self.proj, rel))), rel)

    def test_fora_de_projeto_do_metodo_passa(self):
        self.assertIsNone(so_subagente_edita.decidir(self.e(self.fora)))

    def test_saida_do_script(self):
        cod, out = rodar("so_subagente_edita.py", json.dumps(self.e(os.path.join(self.proj, "src", "a.py"))))
        self.assertEqual(cod, 0)
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "deny")


class ContextoBaixo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "sessoes"))

    def tearDown(self):
        self.tmp.cleanup()

    def retrato(self, usado, gravado_em=None):
        with open(os.path.join(self.tmp.name, "sessoes", "s1.json"), "w") as f:
            json.dump({"gravado_em": gravado_em or time.time(), "context_window": {"used_percentage": usado}}, f)

    def test_avisa_uma_vez_por_limiar(self):
        self.retrato(50)
        self.assertIsNone(contexto_baixo.aviso({"session_id": "s1"}, self.tmp.name))
        self.retrato(72)
        self.assertIn("session-handoff", contexto_baixo.aviso({"session_id": "s1"}, self.tmp.name))
        self.assertIsNone(contexto_baixo.aviso({"session_id": "s1"}, self.tmp.name))
        self.retrato(90)
        self.assertIn("90%", contexto_baixo.aviso({"session_id": "s1"}, self.tmp.name))
        self.assertIsNone(contexto_baixo.aviso({"session_id": "s1"}, self.tmp.name))

    def test_ignora_retrato_velho_e_subagente(self):
        self.retrato(95, gravado_em=time.time() - 3600)
        self.assertIsNone(contexto_baixo.aviso({"session_id": "s1"}, self.tmp.name))
        self.retrato(95)
        self.assertIsNone(contexto_baixo.aviso({"session_id": "s1", "agent_id": "a"}, self.tmp.name))

    def test_script_sem_retrato_fica_quieto(self):
        self.assertEqual(rodar("contexto_baixo.py", json.dumps({"session_id": "nada"}),
                               {"CLAUDE_LIMITES_DIR": self.tmp.name}), (0, ""))


if __name__ == "__main__":
    unittest.main()
