"""Aba Perguntas (perguntas.json, respostas com alternativas), consumo de tokens incremental e previsão."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import analisadores as a
import fontes


def linha_ass(mid, modelo, ent, sai, cr=0, cc=0, ts="2026-11-01T10:00:00Z"):
    return json.dumps({"type": "assistant", "timestamp": ts, "message": {
        "id": mid, "model": modelo, "usage": {"input_tokens": ent, "output_tokens": sai,
                                              "cache_read_input_tokens": cr, "cache_creation_input_tokens": cc}}}) + "\n"


class TestConsumoIncremental(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p = os.path.join(self.tmp, "agent-x.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def escrever(self, texto, modo="a"):
        with open(self.p, modo) as f:
            f.write(texto)

    def test_soma_dedup_por_mensagem_e_por_modelo(self):
        self.escrever(linha_ass("m1", "claude-sonnet-5-5", 2, 100, 50, 10, "2026-11-01T10:00:00Z")
                      + linha_ass("m1", "claude-sonnet-5-5", 2, 100, 50, 10, "2026-11-01T10:00:01Z")  # mesmo id: um bloco a mais
                      + json.dumps({"type": "user", "timestamp": "2026-11-01T10:00:02Z"}) + "\n"
                      + linha_ass("m2", "claude-opus-5-5", 1, 20, 0, 0, "2026-11-01T10:05:00Z")
                      + linha_ass("m3", "<synthetic>", 0, 0, 0, 0, "2026-11-01T10:06:00Z"))
        e = fontes.ler_uso({}, self.p)
        self.assertEqual(e["tot"], {"entrada": 3, "saida": 120, "cache_lido": 50, "cache_criado": 10})
        self.assertEqual(e["modelos"]["claude-sonnet-5-5"]["saida"], 100)
        self.assertEqual(e["modelos"]["claude-opus-5-5"]["saida"], 20)
        self.assertNotIn("<synthetic>", e["modelos"])
        self.assertEqual(e["fim"] - e["ini"], 360)  # do primeiro ao último timestamp de assistente

    def test_arquivo_que_cresce_le_so_o_novo_e_espera_linha_inteira(self):
        self.escrever(linha_ass("m1", "s", 1, 10))
        e = fontes.ler_uso({}, self.p)
        pos = e["pos"]
        meia = linha_ass("m2", "s", 1, 5)
        self.escrever(meia[:20])  # linha pela metade: não conta nem avança
        e = fontes.ler_uso(e, self.p)
        self.assertEqual((e["tot"]["saida"], e["pos"]), (10, pos))
        self.escrever(meia[20:] + linha_ass("m1", "s", 1, 10))  # m1 repetido depois continua deduplicado
        e = fontes.ler_uso(e, self.p)
        self.assertEqual(e["tot"]["saida"], 15)
        self.assertEqual(e["pos"], os.path.getsize(self.p))

    def test_arquivo_trocado_recomeca(self):
        self.escrever(linha_ass("m1", "s", 1, 10) + linha_ass("m2", "s", 1, 10))
        e = fontes.ler_uso({}, self.p)
        self.escrever(linha_ass("m9", "s", 1, 7), "w")  # menor que a posição guardada
        e = fontes.ler_uso(e, self.p)
        self.assertEqual(e["tot"]["saida"], 7)

    def test_linha_quebrada_nao_derruba(self):
        self.escrever('{"type":"assistant", "usage" quebrado\n' + linha_ass("m1", "s", 1, 4))
        self.assertEqual(fontes.ler_uso({}, self.p)["tot"]["saida"], 4)


class TestConsumoDaSessao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sd = os.path.join(self.tmp, "sess")
        os.makedirs(self.sd + "/subagents/workflows/wf_a")
        os.makedirs(self.sd + "/workflows")
        with open(self.sd + ".jsonl", "w") as f:
            f.write(linha_ass("p1", "claude-opus-5-5", 1, 1000, ts="2026-11-01T08:00:00Z"))
        with open(self.sd + "/subagents/agent-av.jsonl", "w") as f:
            f.write(linha_ass("a1", "claude-sonnet-5-5", 1, 200, ts="2026-11-01T09:00:00Z")
                    + linha_ass("a2", "claude-sonnet-5-5", 1, 1, ts="2026-11-01T09:30:00Z"))
        with open(self.sd + "/subagents/workflows/wf_a/agent-w1.jsonl", "w") as f:
            f.write(linha_ass("w1", "claude-haiku-5", 1, 30, ts="2026-11-01T10:00:00Z")
                    + linha_ass("w2", "claude-haiku-5", 1, 30, ts="2026-11-01T10:10:00Z"))
        with open(self.sd + "/workflows/wf_a.json", "w") as f:
            json.dump({"workflowName": "fazer-revisar"}, f)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_totais_por_origem_workflow_modelo_e_tempo(self):
        cache = {}
        c = fontes.consumo(self.sd, cache, agora=a.iso_ts("2026-11-01T12:00:00Z"))
        self.assertEqual(c["total"]["saida"], 1261)
        self.assertEqual(c["total"]["tokens"], 1261 + 5)
        self.assertEqual({o["origem"]: o["tokens"] for o in c["origens"]}, {"principal": 1001, "avulsos": 203, "workflows": 62})
        self.assertEqual(c["workflows"][0]["nome"], "fazer-revisar")
        self.assertEqual((c["workflows"][0]["tokens"], c["workflows"][0]["agentes"], c["workflows"][0]["segundos"]), (62, 1, 600))
        self.assertEqual(c["modelos"]["claude-sonnet-5-5"]["tokens"], 203)
        self.assertEqual(c["agentes"], {"av": 203, "w1": 62})  # tokens por agente (id do arquivo), sem a conversa principal
        self.assertEqual(c["agentes_segundos"], 1800 + 600)  # avulsos + workflows; a conversa principal não entra
        self.assertEqual(c["real_segundos"], 4 * 3600)  # desde o primeiro timestamp da conversa principal
        # segunda passada não relê nada (posições guardadas) e dá o mesmo
        self.assertEqual(fontes.consumo(self.sd, cache, agora=a.iso_ts("2026-11-01T12:00:00Z"))["total"], c["total"])


class TestPrevisao(unittest.TestCase):
    def test_base_do_calculo(self):
        tar = [{"estado": "concluida"}] * 4 + [{"estado": "andando"}] * 2 + [{"estado": "fila"}] * 2 + [{"estado": "bloqueada"}]
        p = a.previsao(tar, real_s=8 * 3600, agentes_s=16 * 3600, baterias_fila=2, bateria_s=[1800, 1200, 600],
                       fase_final_h=1.5, agora=0)
        # 8 h reais / 4 concluídas = 2 h por tarefa; 4 restantes (bloqueada fora) = 8 h; 2 baterias × mediana 20 min; fase final 1,5 h
        self.assertAlmostEqual(p["horas"], 8 + 2 * 1200 / 3600 + 1.5)
        self.assertEqual(p["conclusao_em"], round(p["horas"] * 3600))
        self.assertEqual(p["restantes"], 4)
        self.assertEqual(p["bloqueadas"], 1)
        self.assertAlmostEqual(p["paralelo"], 2.0)
        self.assertTrue(any("mediana" in b for b in p["base"]))

    def test_sem_concluida_nao_divide_por_zero(self):
        p = a.previsao([{"estado": "fila"}], real_s=3600, agentes_s=0, baterias_fila=0, bateria_s=[], fase_final_h=1, agora=0)
        self.assertIsNone(p["horas"])
        self.assertTrue(p["base"])


class TestRitmoDaSessao(unittest.TestCase):
    def test_merges_desde_o_inicio(self):
        linhas = "200|chore(merge): A e B (T158, T141)\n50|chore(merge): velho (T120)\n150|chore(merge): dev na branch\n100|fix: T130"
        self.assertEqual(a.tarefas_dos_merges(linhas, inicio=100), {158, 141, 130})

    def test_ritmo_usa_so_as_concluidas_na_sessao(self):
        tar = [{"id": i, "estado": "concluida"} for i in (1, 2, 3, 4)] + [{"id": 5, "estado": "fila"}]
        p = a.previsao(tar, real_s=4 * 3600, agentes_s=0, baterias_fila=0, bateria_s=[], fase_final_h=0,
                       agora=0, feitas_na_sessao={3, 4})
        # 4 h / 2 da sessão = 2 h por tarefa (e não 1 h, contando as 2 de sessões anteriores); 1 restante
        self.assertAlmostEqual(p["horas"], 2)
        self.assertTrue(any("desta sessão" in b and "parado" in b for b in p["base"]))

    def test_nenhuma_na_sessao_sem_ritmo(self):
        p = a.previsao([{"id": 1, "estado": "concluida"}, {"id": 2, "estado": "fila"}], real_s=3600, agentes_s=0,
                       baterias_fila=0, bateria_s=[], fase_final_h=0, agora=0, feitas_na_sessao=set())
        self.assertIsNone(p["horas"])


class TestCriteriosDaSessao(unittest.TestCase):
    def test_data_e_sha_alem_do_merge(self):
        import datetime
        ini = datetime.datetime(2026, 10, 31, 20, 0).timestamp()
        c = lambda i, e, t: {"id": i, "estado": e, "estado_texto": t}
        tar = [c(1, "concluida", "NA `dev` (31/10): migration"),
               c(2, "concluida", "feita e na `dev` (30/10, `abcdef1`)"),
               c(3, "concluida", "NA `dev` (1º/11, `e2400435`)"),
               c(4, "concluida", "na `dev` (`4b5ad9ce`, 30/10)"),
               c(5, "andando", "em andamento (31/10)"),
               c(6, "concluida", "na dev, sem data"),
               c(7, "concluida", "na `dev` (29/10)")]
        r = a.feitas_da_sessao(tar, {7}, ini, {"abcdef1ffff0", "e2400435aaaa"})
        self.assertEqual(r, {7: "merge", 1: "data", 3: "data", 2: "sha"})

    def test_base_conta_por_criterio(self):
        tar = [{"id": i, "estado": "concluida"} for i in (1, 2, 3)] + [{"id": 4, "estado": "fila"}]
        p = a.previsao(tar, real_s=3600, agentes_s=0, baterias_fila=0, bateria_s=[], fase_final_h=0, agora=0,
                       feitas_na_sessao={1: "merge", 2: "data", 3: "sha"})
        self.assertTrue(any("1 por merge" in b and "1 pelo Estado datado" in b and "1 por sha" in b for b in p["base"]))


class TestPerguntasSemDuvidasMd(unittest.TestCase):
    def test_sem_duvidas_md_mostra_o_json(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        arq = os.path.join(d, "perguntas.json")
        with open(arq, "w") as f:
            json.dump(TestPerguntasJson.BOA, f)
        lista, _ = fontes.perguntas({"projeto": d}, arq)
        self.assertEqual([x["id"] for x in lista], ["D-37"])


class TestPerguntasJson(unittest.TestCase):
    BOA = [{"id": "D-37", "header": "Ordem", "pergunta": "Qual primeiro?", "multiplas": False,
            "opcoes": [{"rotulo": "B", "descricao": "b"}, {"rotulo": "A", "descricao": "a", "recomendada": True}],
            "contexto": "porque sim"}]

    def test_le_valida_e_poe_recomendada_primeiro(self):
        ps, avisos = a.parse_perguntas(json.dumps(self.BOA + [{"id": "x"}, "lixo", {"id": "D-1", "pergunta": "?", "opcoes": [{"rotulo": ""}]}]))
        self.assertEqual([p["id"] for p in ps], ["D-37"])
        self.assertEqual([o["rotulo"] for o in ps[0]["opcoes"]], ["A", "B"])
        self.assertEqual(len(avisos), 3)

    def test_json_invalido_vazio_com_aviso(self):
        ps, avisos = a.parse_perguntas("{nao")
        self.assertEqual(ps, [])
        self.assertIn("perguntas.json", avisos[0])
        self.assertEqual(a.parse_perguntas("[]"), ([], []))

    def test_rotulo_repetido_reprova(self):
        q = dict(self.BOA[0], opcoes=[{"rotulo": "A"}, {"rotulo": "A"}])
        self.assertEqual(a.parse_perguntas(json.dumps([q]))[0], [])

    def test_mescla_com_duvidas_md(self):
        md = ("### D-37. Ordem\n- Situação: x\n\n### D-38. Outra\n- Situação: y\n- (a) um; (b) dois\n\n"
              "### D-39. Feita\n- Situação: z\n- **Resposta:** foi\n")
        ps, _ = a.parse_perguntas(json.dumps(self.BOA + [dict(self.BOA[0], id="D-39")]))
        m = a.mesclar_perguntas(ps, md)
        self.assertEqual([(x["id"], x["fonte"]) for x in m], [("D-37", "json"), ("D-38", "md")])  # D-39 respondida no md some
        d38 = m[1]
        self.assertEqual([o["rotulo"] for o in d38["opcoes"]], ["um", "dois"])
        self.assertEqual(d38["opcoes"][0]["letra"], "a")
        self.assertFalse(d38["multiplas"])


class TestRespostaComAlternativas(unittest.TestCase):
    ABERTAS = [
        {"id": "D-37", "titulo": "Ordem", "pergunta": "Qual?", "multiplas": False, "fonte": "json",
         "opcoes": [{"rotulo": "A", "descricao": ""}, {"rotulo": "B", "descricao": ""}]},
        {"id": "D-40", "titulo": "Quais", "pergunta": "Quais?", "multiplas": True, "fonte": "json",
         "opcoes": [{"rotulo": "X", "descricao": ""}, {"rotulo": "Y", "descricao": ""}]},
    ]

    def ok(self, corpo):
        erro, r = a.validar_resposta(corpo, self.ABERTAS)
        self.assertIsNone(erro, erro)
        return r

    def erro(self, corpo):
        erro, r = a.validar_resposta(corpo, self.ABERTAS)
        self.assertIsNotNone(erro)
        self.assertIsNone(r)

    def test_validas(self):
        r = self.ok({"id": "D-37", "opcoes": ["A"]})
        self.assertEqual((r["opcoes"], r["pergunta"], r["outro"], r["texto"]), (["A"], "Qual?", "", ""))
        self.assertEqual(self.ok({"id": "D-40", "opcoes": ["X", "Y"], "texto": " ok "})["texto"], "ok")
        self.assertEqual(self.ok({"id": "D-37", "opcoes": [], "outro": "nenhuma"})["outro"], "nenhuma")

    def test_invalidas(self):
        self.erro({"id": "D-37", "opcoes": ["A", "B"]})  # escolha única
        self.erro({"id": "D-37", "opcoes": ["Z"]})
        self.erro({"id": "D-40", "opcoes": ["X", "X"]})
        self.erro({"id": "D-37", "opcoes": "A"})
        self.erro({"id": "D-37", "opcoes": [1]})
        self.erro({"id": "D-37", "opcoes": []})  # nada escolhido nem escrito
        self.erro({"id": "D-37", "opcoes": [], "outro": "x" * 2001})
        self.erro({"id": "D-37", "opcoes": [], "outro": "a\u202eb"})
        self.erro({"id": "D-37", "opcoes": ["A"] * 50})


import servidor as s  # noqa: E402
import test_servidor as ts  # noqa: E402


class TestServidorPerguntas(ts.Base):
    def test_abertas_le_perguntas_json_e_post_com_alternativas(self):
        proj = os.path.join(self.tmp, "proj")
        os.makedirs(proj)
        with open(proj + "/duvidas.md", "w") as f:
            f.write("### D-38. Outra\n- Situação: y\n- (a) um; (b) dois\n")
        with open(self.tmp + "/perguntas.json", "w") as f:
            json.dump(TestPerguntasJson.BOA, f)
        orig = (s.CFG, getattr(s, "PERGUNTAS", None))
        s.CFG, s.PERGUNTAS = {**s.CFG, "projeto": proj}, self.tmp + "/perguntas.json"
        try:
            s._abertas = self.orig[2]  # o de verdade, não o do Base
            self.assertEqual([x["id"] for x in s._abertas()], ["D-37", "D-38"])
            r = self.post({"id": "D-37", "opcoes": ["A"], "outro": "", "texto": "vai"})
            self.assertEqual(r.status, 200, r.corpo)
            self.assertEqual(self.post({"id": "D-37", "opcoes": ["A", "B"]}).status, 400)
            self.assertEqual(self.post({"id": "D-38", "opcao": "b"}).status, 200)  # o formato de antes continua
        finally:
            s.CFG, s.PERGUNTAS = orig
        gravadas = [json.loads(Path(s.RESPOSTAS, "pendentes", n).read_text()) for n in sorted(os.listdir(os.path.join(s.RESPOSTAS, "pendentes")))]
        self.assertEqual((gravadas[0]["opcoes"], gravadas[0]["pergunta"], gravadas[0]["texto"]), (["A"], "Qual primeiro?", "vai"))
        self.assertEqual(gravadas[1]["opcao_texto"], "dois")


if __name__ == "__main__":
    unittest.main()
