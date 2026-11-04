"""Quadro 'Rodando agora': comando do eval, mascaramento, descrição pelo .jsonl, estado dos terminados, /proc falso."""
import json
import os
import shutil
import tempfile
import time
import unittest

import shells as sh

SNAP = "source /h/.claude/shell-snapshots/snapshot-zsh-1.sh 2>/dev/null || true && setopt NO_EXTENDED_GLOB 2>/dev/null || true && "
FIM = " < /dev/null && pwd -P >| /tmp/claude-ab12-cwd"


class Comando(unittest.TestCase):
    def test_aspas_simples(self):
        self.assertEqual(sh.extrair_comando(SNAP + "eval 'cd /a && make test'" + FIM), "cd /a && make test")

    def test_aspas_dentro_do_comando(self):
        self.assertEqual(sh.extrair_comando(SNAP + "eval 'echo '\"'\"'oi'\"'\"''" + FIM), "echo 'oi'")

    def test_sem_aspas(self):
        self.assertEqual(sh.extrair_comando(SNAP + "eval /x/esperar_resposta.py" + FIM), "/x/esperar_resposta.py")

    def test_varias_linhas_e_eval_dentro_do_comando(self):
        self.assertEqual(sh.extrair_comando(SNAP + "eval 'a\neval b'" + FIM), "a\neval b")

    def test_sem_eval(self):
        self.assertIsNone(sh.extrair_comando("source x"))


class Mascara(unittest.TestCase):
    def nao_vaza(self, texto, segredo):
        m = sh.mascarar(texto)
        self.assertNotIn(segredo, m, m)
        return m

    def test_bearer_e_authorization(self):
        self.nao_vaza('curl -H "Authorization: Bearer abcDEF123456.xyz" https://x', "abcDEF123456")
        self.nao_vaza("curl -H 'authorization: Basic dXNlcjpwYXNz'", "dXNlcjpwYXNz")
        self.nao_vaza("Bearer abcdefghijkl12345", "abcdefghijkl12345")

    def test_jwt(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJl"
        self.nao_vaza("echo " + jwt, jwt)
        self.nao_vaza("echo " + jwt, "eyJzdWIi")

    def test_chaves_nomeadas(self):
        self.nao_vaza("apikey=segredo1234", "segredo1234")
        self.nao_vaza("SUPABASE_SERVICE_ROLE_KEY=abc999xyz curl", "abc999xyz")
        self.nao_vaza('curl "https://x/?token=zzz888&a=1"', "zzz888")
        self.nao_vaza("senha: minhasenha1", "minhasenha1")
        self.nao_vaza("chave=umachave77", "umachave77")
        self.nao_vaza("login --password hunter2xx", "hunter2xx")
        self.nao_vaza('{"api_key": "aaa111bbb"}', "aaa111bbb")

    def test_prefixos_de_token(self):
        self.nao_vaza("x sk-ant-api03-AbCdEf123456", "AbCdEf123456")
        self.nao_vaza("x ghp_abcdefghij1234567890", "abcdefghij1234567890")
        self.nao_vaza("x sbp_0123456789abcdef0123456789", "0123456789abcdef0123456789")
        self.nao_vaza("x AKIAABCDEFGHIJKLMNOP", "AKIAABCDEFGHIJKLMNOP")

    def test_url_com_senha(self):
        self.nao_vaza("psql postgres://admin:s3nh4forte@db:5432/x", "s3nh4forte")

    def test_cpf_cnpj(self):
        self.nao_vaza("cliente 123.456.789-09 ok", "123.456.789")
        self.nao_vaza("cliente 12345678909 ok", "12345678909")
        self.nao_vaza("empresa 12.345.678/0001-95", "12.345.678")
        self.nao_vaza("empresa 12345678000195", "12345678000195")

    def test_email_e_telefone(self):
        self.nao_vaza("mail fulano.silva@empresa.com.br", "fulano.silva")
        self.nao_vaza("fone (65) 99999-1234", "99999-1234")
        self.nao_vaza("fone +55 65 99999-1234", "99999-1234")

    def test_segredo_longo_sem_nome(self):
        tok = "Zm9vYmFyMTIzNDU2Nzg5MGFiY2RlZmdoaWprbG1ub3BxcnN0"
        self.nao_vaza("echo " + tok, tok)

    def test_usuario_e_senha_do_curl(self):
        self.nao_vaza("curl -u admin:hunter2 https://x", "hunter2")
        self.nao_vaza("curl --user admin:hunter2 https://x", "hunter2")
        self.nao_vaza("curl -u 'admin:hunter2' https://x", "hunter2")
        self.nao_vaza("curl --user=admin:hunter2 https://x", "hunter2")

    def test_cookie(self):
        self.nao_vaza("curl -H 'Cookie: session=abcd1234; outro=zzz9999' https://x", "abcd1234")
        self.nao_vaza("curl -H 'Cookie: session=abcd1234; outro=zzz9999' https://x", "zzz9999")
        self.nao_vaza("Set-Cookie: sid=qq11ww22; Path=/", "qq11ww22")
        self.nao_vaza("curl --cookie 'sid=qq11ww22' https://x", "qq11ww22")

    def test_senha_colada_no_p_do_mysql(self):
        self.nao_vaza("mysql -u root -p'minhasenha' db", "minhasenha")
        self.nao_vaza("mysql -u root -pminhasenha db", "minhasenha")

    def test_senha_sem_igual_nem_dois_pontos(self):
        self.nao_vaza("login password hunter2xx", "hunter2xx")
        self.nao_vaza("usar senha abc12345 agora", "abc12345")

    def test_valor_entre_aspas_com_espaco(self):
        self.nao_vaza('secret_key="aaa bbb ccc"', "bbb")
        self.nao_vaza('secret_key="aaa bbb ccc"', "ccc")
        self.nao_vaza("password='uma frase longa'", "frase")
        self.nao_vaza("TOKEN='x y z'", "y z")

    def test_texto_comum_fica(self):
        for t in ("git checkout -b feat/x", "git push -u origin dev", "ls -la /tmp", "mkdir -p /tmp/x", "tar -xzf a.tgz",
                  "grep -rn foo .", "ps -u root", "cd /x/wt/t140 && scripts/testar_como_o_ci.py", "feat/t140-assistente", "saida=0",
                  "6e81ff34-0b44-4d05-af57-110c155da013", "a" * 10 + " " + "1793434817", "d0f8a8f1c5d0e5b7a1c2d3e4f5a6b7c8d9e0f1a2"):
            self.assertEqual(sh.mascarar(t), t)


def linha(obj):
    return json.dumps(obj, ensure_ascii=False) + "\n"


def uso(tid, desc, cmd, bg=True, ts="2026-11-01T10:00:00.000Z"):
    inp = {"command": cmd, "description": desc}
    if bg:
        inp["run_in_background"] = True
    return linha({"type": "assistant", "timestamp": ts, "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": tid, "name": "Bash", "input": inp}]}})


def resultado(tid, task, sid="S1"):
    txt = f"Command running in background with ID: {task}. Output is being written to: /tmp/x/{sid}/tasks/{task}.output."
    return linha({"type": "user", "message": {"role": "user", "content": [
        {"tool_use_id": tid, "type": "tool_result", "content": txt, "is_error": False}]}})


def nota(task, status, resumo, ts="2026-11-01T10:30:00.000Z"):
    return linha({"type": "queue-operation", "operation": "enqueue", "timestamp": ts, "content":
                  f"<task-notification>\n<task-id>{task}</task-id>\n<tool-use-id>t</tool-use-id>\n<output-file>/x</output-file>\n"
                  f"<status>{status}</status>\n<summary>{resumo}</summary>\n</task-notification>"})


class LerJsonl(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.arq = os.path.join(self.tmp, "s.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def grava(self, *ls, modo="a"):
        with open(self.arq, modo) as f:
            f.write("".join(ls))

    def test_task_id_para_descricao_e_comando(self):
        self.grava(uso("u1", "Rodar a bateria da T140", "scripts/testar_como_o_ci.py"), resultado("u1", "bab12cd"),
                   uso("u2", "ls rápido", "ls", bg=False), linha({"type": "summary"}))
        est = sh.ler_shells(None, self.arq)
        self.assertEqual(set(est["tasks"]), {"bab12cd"})
        t = est["tasks"]["bab12cd"]
        self.assertEqual((t["descricao"], t["comando"]), ("Rodar a bateria da T140", "scripts/testar_como_o_ci.py"))
        self.assertGreater(t["inicio"], 0)

    def test_notificacoes(self):
        self.grava(uso("u1", "a", "a"), resultado("u1", "b1"), uso("u2", "b", "b"), resultado("u2", "b2"),
                   uso("u3", "c", "c"), resultado("u3", "b3"), nota("b1", "killed", "Background command \"Esperar\" was stopped because the system is running low on memory"),
                   nota("b2", "failed", "Background command x failed with exit code 3"), nota("b3", "completed", "ok"))
        n = sh.ler_shells(None, self.arq)["notas"]
        self.assertEqual({k: v["status"] for k, v in n.items()}, {"b1": "killed", "b2": "failed", "b3": "completed"})
        self.assertIn("low on memory", n["b1"]["resumo"])
        self.assertIn('"Esperar"', n["b1"]["resumo"])  # o JSON escapado volta ao texto
        self.assertGreater(n["b1"]["quando"], 0)

    def test_nota_citada_ou_de_task_desconhecida_nao_vale(self):
        n = nota("b1", "killed", "low on memory")
        citada = linha({"type": "assistant", "timestamp": "2026-11-01T10:31:00.000Z", "message": {"role": "assistant", "content": [
            {"type": "text", "text": json.loads(n)["content"]}]}})
        eco = linha({"type": "api-request-blob", "message": {"content": json.loads(n)["content"]}})
        no_meio = linha({"type": "user", "message": {"role": "user", "content": "veja: " + json.loads(n)["content"]}})
        self.grava(uso("u1", "a", "a"), resultado("u1", "b1"), citada, eco, no_meio, nota("bzz", "killed", "x"))
        self.assertEqual(sh.ler_shells(None, self.arq)["notas"], {})

    def test_nota_vinda_como_mensagem_de_usuario_vale(self):
        n = json.loads(nota("b1", "failed", "exit code 2"))["content"]
        self.grava(uso("u1", "a", "a"), resultado("u1", "b1"),
                   linha({"type": "user", "timestamp": "2026-11-01T10:31:00.000Z", "message": {"role": "user", "content": n}}))
        self.assertEqual(sh.ler_shells(None, self.arq)["notas"]["b1"]["status"], "failed")

    def test_leitura_em_pedacos_pequenos_da_o_mesmo_resultado(self):
        self.grava(*[uso(f"u{i}", f"tarefa {i}", "c" * 700) + resultado(f"u{i}", f"b{i}") + linha({"type": "summary", "x": "y" * 300})
                     for i in range(6)], nota("b5", "completed", "ok"))
        inteiro = sh.ler_shells(None, self.arq)
        antes, sh.PEDACO = sh.PEDACO, 256
        try:
            pedacos = sh.ler_shells(None, self.arq)
        finally:
            sh.PEDACO = antes
        self.assertEqual(pedacos, inteiro)
        self.assertEqual(pedacos["pos"], os.path.getsize(self.arq))
        self.assertEqual(len(pedacos["tasks"]), 6)

    def test_nunca_le_mais_que_um_pedaco_de_uma_vez(self):
        self.grava(*[uso(f"u{i}", "x", "c" * 500) + resultado(f"u{i}", f"b{i}") for i in range(20)])
        lidos, aberto = [], open

        class Espia:
            def __init__(self, f): self.f = f
            def __enter__(self): return self
            def __exit__(self, *a): self.f.close()
            def seek(self, *a): return self.f.seek(*a)
            def read(self, n=-1):
                lidos.append(n)
                return self.f.read(n)

        antes, sh.PEDACO = sh.PEDACO, 1024
        try:
            from unittest import mock
            with mock.patch("shells.open", lambda *a, **k: Espia(aberto(*a, **k)), create=True):
                est = sh.ler_shells(None, self.arq)
        finally:
            sh.PEDACO = antes
        self.assertEqual(len(est["tasks"]), 20)
        self.assertTrue(lidos and all(0 < n <= 1024 for n in lidos), lidos)

    def test_linha_gigante_e_descartada_e_a_seguinte_le(self):
        self.grava(uso("u1", "a", "a"), resultado("u1", "b1"), linha({"type": "api-request-blob", "x": "z" * 5000, "t": "run_in_background"}),
                   uso("u2", "b", "b"), resultado("u2", "b2"))
        a1, a2 = sh.PEDACO, sh.LINHA_MAX
        sh.PEDACO, sh.LINHA_MAX = 256, 1024
        try:
            est = sh.ler_shells(None, self.arq)
        finally:
            sh.PEDACO, sh.LINHA_MAX = a1, a2
        self.assertEqual(set(est["tasks"]), {"b1", "b2"})
        self.assertEqual(est["pos"], os.path.getsize(self.arq))

    def test_incremental_e_linha_pela_metade(self):
        self.grava(uso("u1", "um", "a"), resultado("u1", "b1"))
        est = sh.ler_shells(None, self.arq)
        meia = uso("u2", "dois", "b") + resultado("u2", "b2")
        self.grava(meia[:-30])  # a última linha ainda não terminou
        est = sh.ler_shells(est, self.arq)
        self.assertEqual(set(est["tasks"]), {"b1"})
        self.grava(meia[-30:])
        est = sh.ler_shells(est, self.arq)
        self.assertEqual(set(est["tasks"]), {"b1", "b2"})

    def test_arquivo_trocado_recomeca(self):
        self.grava(uso("u1", "um", "a"), resultado("u1", "b1"))
        est = sh.ler_shells(None, self.arq)
        self.grava(uso("u9", "nove", "z"), resultado("u9", "b9"), modo="w")
        os.replace(self.arq, self.arq + ".x")  # outro inode
        self.grava(uso("u9", "nove", "z"), resultado("u9", "b9"), modo="w")
        self.assertEqual(set(sh.ler_shells(est, self.arq)["tasks"]), {"b9"})

    def test_linha_corrompida_nao_derruba(self):
        self.grava("run_in_background {{{\n", uso("u1", "um", "a"), resultado("u1", "b1"))
        self.assertEqual(set(sh.ler_shells(None, self.arq)["tasks"]), {"b1"})


class EstadoTerminado(unittest.TestCase):
    def test_codigo_zero(self):
        self.assertEqual(sh.estado_terminado("x\n[exited with code 0]\n", None)["estado"], "terminou")

    def test_codigo_diferente_de_zero(self):
        r = sh.estado_terminado("x\n[exited with code 4]\n", None)
        self.assertEqual((r["estado"], r["codigo"]), ("falhou", 4))

    def test_morto_por_memoria(self):
        r = sh.estado_terminado("", {"status": "killed", "resumo": "stopped because the system is running low on memory"})
        self.assertEqual(r["estado"], "memoria")

    def test_morto_a_pedido(self):
        r = sh.estado_terminado("", {"status": "killed", "resumo": "Background command was stopped"})
        self.assertEqual(r["estado"], "parado")

    def test_nota_vale_mais_que_a_saida(self):
        r = sh.estado_terminado("[exited with code 0]", {"status": "killed", "resumo": "low on memory"})
        self.assertEqual(r["estado"], "memoria")

    def test_so_a_nota_failed_traz_o_codigo(self):
        r = sh.estado_terminado("", {"status": "failed", "resumo": "Background command x failed with exit code 7"})
        self.assertEqual((r["estado"], r["codigo"]), ("falhou", 7))

    def test_sem_sinal_nenhum(self):
        self.assertIsNone(sh.estado_terminado("ainda escrevendo", None))


class Coletar(unittest.TestCase):
    SID = "6e81ff34-0b44-4d05-af57-110c155da013"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        t = self.tmp
        self.cfg = {"sessoes": t + "/sessoes", "saidas": t + "/saidas"}
        os.makedirs(self.cfg["sessoes"] + "/" + self.SID)
        self.tasks = f"{t}/saidas/{self.SID}/tasks"
        os.makedirs(self.tasks)
        self.proc = t + "/proc"
        os.makedirs(self.proc)
        with open(self.proc + "/uptime", "w") as f:
            f.write("10000.50 9000.00\n")
        self.jsonl = f"{self.cfg['sessoes']}/{self.SID}.jsonl"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def processo(self, pid, script, task, inicio_s=9000.0, argv0="/usr/bin/zsh", saida=True):
        d = f"{self.proc}/{pid}"
        os.makedirs(d + "/fd")
        with open(d + "/cmdline", "wb") as f:
            f.write(b"\0".join(x.encode() for x in (argv0, "-c", script)) + b"\0")
        campos = ["S", "1", "1", "1", "0", "-1", "0", "0", "0", "0", "0", "0", "0", "0", "0", "20", "0", "1", "0", str(int(inicio_s * 100))]
        with open(d + "/stat", "w") as f:
            f.write(f"{pid} (zsh) " + " ".join(campos) + " 0 0\n")
        if saida:
            os.symlink(f"{self.tasks}/{task}.output", d + "/fd/1")

    def saida(self, task, texto):
        with open(f"{self.tasks}/{task}.output", "w") as f:
            f.write(texto)

    def coleta(self):
        return sh.coletar(self.cfg, {}, self.cfg["sessoes"] + "/" + self.SID, self.proc, time.time())

    def test_shell_rodando_com_descricao_tempo_e_saida(self):
        with open(self.jsonl, "w") as f:
            f.write(uso("u1", "Esperar a bateria da T140", "sleep 99") + resultado("u1", "bab12cd"))
        self.processo(10, SNAP + "eval 'until false; do sleep 5; done'" + FIM, "bab12cd")
        self.saida("bab12cd", "\n".join(f"linha {i}" for i in range(20)) + "\n")
        r = self.coleta()
        self.assertEqual(len(r["rodando"]), 1)
        x = r["rodando"][0]
        self.assertEqual((x["id"], x["descricao"], x["comando"]), ("bab12cd", "Esperar a bateria da T140", "until false; do sleep 5; done"))
        self.assertAlmostEqual(x["segundos"], 1000.5, delta=0.1)
        self.assertEqual(x["saida"][-1], "linha 19")
        self.assertEqual(len(x["saida"]), 8)
        self.assertEqual(x["sessao"], "6e81ff34")

    def test_ignora_o_que_nao_e_shell_de_fundo(self):
        self.processo(11, SNAP + "eval 'ls'" + FIM, "x1", saida=False)          # primeiro plano: fd/1 não aponta para tasks
        self.processo(12, "echo oi", "x2")                                        # não é o zsh -c do Claude
        os.makedirs(self.proc + "/abc")                                           # entrada que não é pid
        self.assertEqual(self.coleta()["rodando"], [])

    def test_sem_descricao_no_jsonl_usa_o_comando(self):
        self.processo(10, SNAP + "eval 'sleep 1'" + FIM, "bzzzz")
        self.saida("bzzzz", "")
        x = self.coleta()["rodando"][0]
        self.assertEqual((x["descricao"], x["comando"]), ("", "sleep 1"))

    def test_comando_de_agente_curto_sem_descricao_nao_vira_ruido(self):
        with open(self.jsonl, "w") as f:
            f.write(uso("u1", "Esperar", "sleep 9") + resultado("u1", "bfundo"))
        self.processo(10, SNAP + "eval 'ls'" + FIM, "bcurto", inicio_s=9998.0)    # 2,5 s, não está no .jsonl: é de um agente
        self.processo(11, SNAP + "eval 'sleep 9'" + FIM, "bfundo", inicio_s=9999.0)  # 1,5 s mas é shell de fundo da sessão
        self.processo(12, SNAP + "eval 'make'" + FIM, "blongo", inicio_s=9000.0)     # longo, sem descrição: aparece
        r = {x["id"]: x for x in self.coleta()["rodando"]}
        self.assertEqual(set(r), {"bfundo", "blongo"})
        self.assertEqual((r["bfundo"]["fundo"], r["blongo"]["fundo"]), (True, False))

    def test_terminados(self):
        with open(self.jsonl, "w") as f:
            f.write(uso("u1", "Bateria da T140", "b1cmd", ts="2026-11-01T10:00:00.000Z") + resultado("u1", "b1")
                    + uso("u2", "Esperar respostas", "esperar", ts="2026-11-01T11:00:00.000Z") + resultado("u2", "b2")
                    + uso("u3", "Subir banco", "banco", ts="2026-11-01T11:10:00.000Z") + resultado("u3", "b3")
                    + uso("u4", "Ainda sem fim", "x", ts="2026-11-01T11:20:00.000Z") + resultado("u4", "b4")
                    + nota("b2", "killed", "stopped because the system is running low on memory", "2026-11-01T11:31:00.000Z"))
        self.saida("b1", "ok\n[exited with code 0]\n")
        self.saida("b3", "erro feio\n[exited with code 4]\n")
        self.saida("b4", "escrevendo\n")
        r = {x["id"]: x for x in self.coleta()["terminados"]}
        self.assertEqual(set(r), {"b1", "b2", "b3"})  # b4 não terminou nem tem aviso: não se afirma nada
        self.assertEqual((r["b1"]["estado"], r["b1"]["descricao"]), ("terminou", "Bateria da T140"))
        self.assertEqual((r["b3"]["estado"], r["b3"]["codigo"]), ("falhou", 4))
        self.assertEqual(r["b2"]["estado"], "memoria")
        self.assertGreater(r["b2"]["quando"], r["b3"]["quando"] - 10 ** 9)
        self.assertEqual(r["b3"]["saida"], ["erro feio", "[exited with code 4]"])
        self.assertAlmostEqual(r["b2"]["duracao"], 31 * 60, delta=1)

    def test_aviso_de_morte_que_chega_depois_da_saida_corrige_o_estado(self):
        cache = {}
        with open(self.jsonl, "w") as f:
            f.write(uso("u1", "Esperar", "x") + resultado("u1", "b1"))
        self.saida("b1", "[exited with code 0]\n")
        coleta = lambda: sh.coletar(self.cfg, cache, self.cfg["sessoes"] + "/" + self.SID, self.proc, time.time())
        self.assertEqual(coleta()["terminados"][0]["estado"], "terminou")
        with open(self.jsonl, "a") as f:
            f.write(nota("b1", "killed", "stopped because the system is running low on memory"))
        self.assertEqual(coleta()["terminados"][0]["estado"], "memoria")

    def test_so_os_10_ultimos_em_ordem(self):
        with open(self.jsonl, "w") as f:
            for i in range(14):
                f.write(uso(f"u{i}", f"tarefa {i}", "c", ts=f"2026-11-01T10:{i:02d}:00.000Z") + resultado(f"u{i}", f"b{i}")
                        + nota(f"b{i}", "completed", "ok", f"2026-11-01T10:{i:02d}:30.000Z"))
        ids = [x["id"] for x in self.coleta()["terminados"]]
        self.assertEqual(ids, [f"b{i}" for i in range(13, 3, -1)])

    def test_rodando_nao_entra_nos_terminados(self):
        with open(self.jsonl, "w") as f:
            f.write(uso("u1", "x", "c") + resultado("u1", "b1") + nota("b1", "killed", "low on memory"))
        self.processo(10, SNAP + "eval 'c'" + FIM, "b1")
        self.saida("b1", "")
        r = self.coleta()
        self.assertEqual(([x["id"] for x in r["rodando"]], r["terminados"]), (["b1"], []))

    def test_nada_sensivel_sai(self):
        cpf = "123.456.789-09"
        cmd = f"curl -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2ln' https://x/?cpf={cpf}"
        with open(self.jsonl, "w") as f:
            f.write(uso("u1", f"Chamar a API do cliente {cpf}", cmd) + resultado("u1", "b1")
                    + uso("u2", "outro", cmd) + resultado("u2", "b2") + nota("b2", "failed", f"falhou {cpf} exit code 1"))
        self.processo(10, SNAP + "eval '" + cmd + "'" + FIM, "b1")
        self.saida("b1", f"token=abc123xyz\nCPF {cpf}\nfulano@x.com.br\n")
        self.saida("b2", f"Bearer abcdefghijkl123\n[exited with code 1]\n")
        r = json.dumps(self.coleta(), ensure_ascii=False)
        for vazou in ("eyJ", "abc123xyz", cpf, "fulano@", "abcdefghijkl123"):
            self.assertNotIn(vazou, r)


class Quadro(unittest.TestCase):
    def test_resumo(self):
        bat = {"rodando": {"wt": "t140", "desde": 100.0}, "fila": ["t166"],
               "logs": [{"wt": "t140", "passo": "testes de tela", "terminou": False}]}
        ags = [{"ativo": True}, {"ativo": False}]
        wfs = [{"rodando": True}, {"rodando": False}]
        q = sh.quadro({"rodando": [1, 2], "terminados": [3]}, bat, ags, wfs)
        self.assertEqual(q["bateria"], {"wt": "t140", "desde": 100.0, "passo": "testes de tela", "fila": ["t166"]})
        self.assertEqual((q["agentes_ativos"], q["workflows_rodando"], q["shells"]["rodando"], q["shells"]["terminados"]), (1, 1, [1, 2], [3]))

    def test_sem_bateria(self):
        q = sh.quadro(None, {"rodando": None, "fila": [], "logs": []}, [], [])
        self.assertIsNone(q["bateria"])
        self.assertEqual(q["shells"], {"rodando": [], "terminados": []})


if __name__ == "__main__":
    unittest.main()
