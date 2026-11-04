"""Testes do install.py: HOME temporário, sem rede, sem claude/npm/uv no PATH.  python3 -m unittest test_install -v"""
import json
import os
import tempfile
import unittest
from pathlib import Path

import install

EXEMPLO = {
    "env": {"A": "exemplo", "B": "so-exemplo"},
    "model": "opus",
    "permissions": {"allow": ["x", "y"]},
    "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]}]},
}


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        t = Path(self._t.name)
        self.raiz, self.home, self.vazio = t / "repo", t / "home", t / "bin"
        for d in (self.raiz, self.home, self.vazio):
            d.mkdir()
        c = self.raiz / "claude"
        (c / "__pycache__").mkdir(parents=True)
        (c / "sub").mkdir()
        (c / "a.txt").write_text("novo")
        (c / "sub" / "b.txt").write_text("b")
        (c / "test_x.py").write_text("t")
        (c / "__pycache__" / "x.pyc").write_text("p")
        (c / "m.pyc").write_text("p")
        (c / "settings.example.json").write_text(json.dumps(EXEMPLO))
        (self.raiz / "painel").mkdir()
        (self.raiz / "painel" / "p.py").write_text("print(1)")
        (self.raiz / "painel" / "test_p.py").write_text("t")
        self.cd = self.home / ".claude"

    def tearDown(self):
        self._t.cleanup()

    def rodar(self, *args, entrada="s"):
        saida = []
        cod = install.main(list(args), home=self.home, raiz=self.raiz, path=str(self.vazio), env={},
                           entrada=lambda _p: entrada, saida=saida.append, orcamento=False)
        return cod, "\n".join(saida)

    def arquivos(self, base):
        return sorted(str(p.relative_to(base)) for p in base.rglob("*") if p.is_file())


class TestInstall(Base):
    def test_dry_run_nao_grava(self):
        cod, out = self.rodar("--dry-run")
        self.assertEqual(cod, 0)
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertIn("[dry-run]", out)

    def test_so_checar_so_reporta(self):
        cod, out = self.rodar("--so-checar")
        self.assertEqual(cod, 0)
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertNotIn("[dry-run]", out)
        self.assertIn("Falta fazer", out)
        self.assertIn("a.txt", out)

    def test_copia_e_exclusoes(self):
        self.rodar("--sem-plugins")
        self.assertEqual(self.arquivos(self.cd),
                         ["a.txt", "settings.example.json", "settings.json", "sub/b.txt"])
        self.assertEqual(self.arquivos(self.home / "painel-da-sessao"), ["p.py"])

    def test_backup_do_que_sera_sobrescrito(self):
        self.cd.mkdir()
        (self.cd / "a.txt").write_text("antigo")
        (self.cd / "sub").mkdir()
        (self.cd / "sub" / "b.txt").write_text("b")  # igual: nao entra no backup
        self.rodar("--sem-plugins")
        self.assertEqual((self.cd / "a.txt").read_text(), "novo")
        bks = list((self.cd / "backups").glob("optimusclaude-*"))
        self.assertEqual(len(bks), 1)
        self.assertEqual(self.arquivos(bks[0]), ["claude/a.txt"])
        self.assertEqual((bks[0] / "claude" / "a.txt").read_text(), "antigo")

    def test_settings_existente_nao_e_mexido_sem_flag(self):
        self.cd.mkdir()
        (self.cd / "settings.json").write_text('{"model": "meu"}')
        self.rodar("--sem-plugins")
        self.assertEqual((self.cd / "settings.json").read_text(), '{"model": "meu"}')

    def test_mescla_preserva_usuario_e_adiciona_exemplo(self):
        self.cd.mkdir()
        usuario = {"model": "meu", "extra": 1, "env": {"A": "meu"},
                   "permissions": {"allow": ["z", "x"]},
                   "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]},
                                            {"matcher": "Read", "hooks": []}]}}
        (self.cd / "settings.json").write_text(json.dumps(usuario))
        self.rodar("--sem-plugins", "--mesclar-settings")
        r = json.loads((self.cd / "settings.json").read_text())
        self.assertEqual(r["model"], "meu")
        self.assertEqual(r["extra"], 1)
        self.assertEqual(r["env"], {"A": "meu", "B": "so-exemplo"})
        self.assertEqual(r["permissions"]["allow"], ["z", "x", "y"])
        self.assertEqual(len(r["hooks"]["PreToolUse"]), 2)  # hook igual nao duplica
        bk = next((self.cd / "backups").glob("optimusclaude-*")) / "settings.json"
        self.assertEqual(json.loads(bk.read_text()), usuario)
        self.rodar("--sem-plugins", "--mesclar-settings")  # idempotente
        self.assertEqual(json.loads((self.cd / "settings.json").read_text()), r)

    def test_mescla_recusada_ou_dry_run_nao_grava(self):
        self.cd.mkdir()
        (self.cd / "settings.json").write_text('{"model": "meu"}')
        self.rodar("--sem-plugins", "--mesclar-settings", entrada="n")
        self.assertEqual((self.cd / "settings.json").read_text(), '{"model": "meu"}')
        self.rodar("--sem-plugins", "--mesclar-settings", "--dry-run")
        self.assertEqual((self.cd / "settings.json").read_text(), '{"model": "meu"}')

    def test_mesclar_funcao(self):
        self.assertEqual(install.mesclar({"a": [1, 2], "k": "ex"}, {"a": [2, 3], "k": "meu"}), {"a": [2, 3, 1], "k": "meu"})

    def test_hook_rtk_formato_inesperado_nao_quebra(self):
        self.cd.mkdir()
        for conteudo in ('{"hooks":{"PreToolUse":[{"hooks":null}]}}', '{"hooks":null}', '[1]'):
            (self.cd / "settings.json").write_text(conteudo)
            cod, out = self.rodar("--sem-plugins")
            self.assertEqual(cod, 0)
            self.assertIn("formato inesperado", out)
            self.assertNotIn("JSON válido", out)
        (self.cd / "settings.json").write_text("{nao json")
        _, out = self.rodar("--sem-plugins")
        self.assertIn("não é um JSON válido", out)

    def test_settings_com_bom(self):
        self.cd.mkdir()
        (self.cd / "settings.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(EXEMPLO).encode())
        _, out = self.rodar("--sem-plugins", "--mesclar-settings")
        self.assertNotIn("JSON válido", out)
        self.assertNotIn("hook do rtk", out)

    def test_mescla_hook_com_matcher_igual_e_hooks_extras_nao_duplica(self):
        rtk = {"type": "command", "command": "rtk hook claude"}
        ex = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [dict(rtk, timeout=5)]},
                                       {"matcher": "Read", "hooks": [{"type": "command", "command": "ler"}]}],
                        "PostToolUse": [{"hooks": [{"type": "command", "command": "ctx"}]}]}}
        user = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [rtk, {"type": "command", "command": "outro"}]}]}}
        r = install.mesclar(ex, user)
        cmds = [h["command"] for e in r["hooks"]["PreToolUse"] for h in e["hooks"]]
        self.assertEqual(cmds, ["rtk hook claude", "outro", "ler"])
        self.assertEqual(len(r["hooks"]["PostToolUse"]), 1)

    def test_nada_a_mesclar_nao_pergunta_nem_grava(self):
        self.cd.mkdir()
        (self.cd / "settings.json").write_text(json.dumps(EXEMPLO))
        self.rodar("--sem-plugins", "--mesclar-settings")  # mescla e grava
        antes = (self.cd / "settings.json").read_text()

        def nao_pergunte(_):
            raise AssertionError("perguntou")
        saida = []
        install.main(["--sem-plugins", "--mesclar-settings"], home=self.home, raiz=self.raiz, path=str(self.vazio),
                     env={}, entrada=nao_pergunte, saida=saida.append, orcamento=False)
        self.assertIn("nada a mesclar", "\n".join(saida))
        self.assertEqual((self.cd / "settings.json").read_text(), antes)

    def test_backup_com_diretorio_unico(self):
        self.cd.mkdir()
        (self.cd / "a.txt").write_text("v1")
        self.rodar("--sem-plugins")
        (self.cd / "a.txt").write_text("v2")
        self.rodar("--sem-plugins")
        bks = sorted((self.cd / "backups").glob("optimusclaude-*"))
        self.assertEqual(len(bks), 2)
        self.assertEqual({(b / "claude" / "a.txt").read_text() for b in bks}, {"v1", "v2"})

    def test_help_descreve_opcoes(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            install.main(["--help"])
        self.assertIn("mostra o que faria", buf.getvalue())
        self.assertIn("mescla settings.example.json", buf.getvalue())

    def test_so_sugere_instaladores_do_sistema(self):
        for so in ("windows", "mac", "linux"):
            for bin_, _, _, inst in install.dependencias(so):
                if bin_ in ("git", "node", "uv"):
                    self.assertIsNone(inst, (so, bin_))

    def test_versao_do_python(self):
        self.assertTrue(install.python_ok((3, 9)))
        self.assertFalse(install.python_ok((3, 8)))

    def test_pipx_so_sugerido(self):
        self.assertEqual(install.dependencias("linux")[5][3], "uvtool:serena-agent")

    def test_opcao_desconhecida(self):
        cod, _ = self.rodar("--nao-existe")
        self.assertEqual(cod, 2)


class SkillsDeTerceiros(Base):
    """O instalador instala as skills de terceiros que o método usa (npx skills add), pulando as que já existem."""

    def npx_falso(self):
        log = self.vazio / "npx.log"
        npx = self.vazio / "npx"
        npx.write_text(f'#!/bin/sh\necho "$@" >> "{log}"\n')
        npx.chmod(0o755)
        return log

    @unittest.skipIf(os.name == "nt", "npx falso é script sh")
    def test_instala_as_que_faltam_e_pula_as_que_existem(self):
        log = self.npx_falso()
        (self.home / ".claude" / "skills" / "grilling").mkdir(parents=True)
        cod, out = self.rodar()
        self.assertEqual(cod, 0)
        chamadas = log.read_text().splitlines()
        alvos = {c.split()[3] for c in chamadas}
        self.assertIn("mattpocock/skills@grill-me", alvos)
        self.assertIn("microsoft/playwright-cli@playwright-cli", alvos)
        self.assertNotIn("mattpocock/skills@grilling", alvos)
        self.assertTrue(all(c.startswith("-y skills add ") and c.endswith(" -g -y") for c in chamadas), chamadas)
        self.assertIn("ok       skill grilling", out)

    @unittest.skipIf(os.name == "nt", "npx falso é script sh")
    def test_dry_run_e_sem_skills_nao_chamam_npx(self):
        log = self.npx_falso()
        cod, out = self.rodar("--dry-run")
        self.assertFalse(log.exists())
        self.assertIn("[dry-run] npx -y skills add mattpocock/skills@grill-me -g -y", out)
        cod, out = self.rodar("--sem-skills")
        self.assertFalse(log.exists())

    def test_sem_npx_vira_falta_fazer(self):
        cod, out = self.rodar()
        self.assertIn("npx -y skills add mattpocock/skills@grill-me -g -y", out.split("Falta fazer")[-1])


if __name__ == "__main__":
    unittest.main()
