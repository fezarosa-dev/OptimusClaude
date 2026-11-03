"""Quadro dos workflows na Visão geral: meta do script, etapa atual, andamento por tarefa e workflow terminado."""
import json
import os
import shutil
import tempfile
import unittest

import workflows as w

SCRIPT = """export const meta = {
  name: 'fazer-revisar-corrigir',
  description: 'Cada tarefa: um agente faz, outro revisa',
  whenToUse: 'name: falso, phases: [{ title: \\'Falso\\' }]',  // comentário com } e {
  phases: [
    { title: 'Fazer', detail: 'um agente por tarefa, } assim' },
    { title: 'Revisar', detail: 'outro agente lê' },
    { title: "Corrigir" },
  ],
}
const X = 1
"""


def j(**e):
    return json.dumps(e) + "\n"


# T1: fez, revisou 1 (achou problema), corrige agora. T2: fazendo agora. T3: ainda não começou.
JOURNAL = (j(type="launched")
           + j(type="started", agentId="a1", label="T1 fazer", phase="Fazer")
           + j(type="started", agentId="a2", label="T2 fazer", phase="Fazer")
           + j(type="result", agentId="a1", result={"status": "pronto"})
           + j(type="started", agentId="a3", label="T1 revisar 1", phase="Revisar")
           + j(type="result", agentId="a3", result={"veredito": "reprovado"})
           + j(type="started", agentId="a4", label="T1 corrigir", phase="Corrigir"))
ARGS = {"tarefas": [{"id": "T1"}, {"id": "T2", "passos": [{"nome": "T2a"}, {"nome": "T2b"}]}, {"id": "T3"}]}


class ParseMeta(unittest.TestCase):
    def test_nome_descricao_e_etapas(self):
        m = w.parse_meta(SCRIPT)
        self.assertEqual(m["name"], "fazer-revisar-corrigir")
        self.assertEqual(m["description"], "Cada tarefa: um agente faz, outro revisa")
        self.assertEqual([(p["title"], p["detail"]) for p in m["phases"]],
                         [("Fazer", "um agente por tarefa, } assim"), ("Revisar", "outro agente lê"), ("Corrigir", "")])

    def test_script_inline_curto(self):
        m = w.parse_meta("export const meta={name:`x`,phases:[{title:'A'},{title:'B'}]}; run()")
        self.assertEqual((m["name"], [p["title"] for p in m["phases"]]), ("x", ["A", "B"]))

    def test_sem_meta(self):
        self.assertEqual(w.parse_meta("const REPO = 1\nawait agent('x')"), {"name": None, "description": "", "phases": []})
        self.assertEqual(w.parse_meta(None)["name"], None)

    def test_meta_quebrado_nao_estoura(self):
        self.assertEqual(w.parse_meta("export const meta = { name: 'abc")["name"], None)

    def test_mascara(self):
        m = w.parse_meta("export const meta = {name: 'x', description: 'chama com token=abc123xyz e fulano@x.com.br'}")
        self.assertNotIn("abc123xyz", m["description"])
        self.assertNotIn("fulano@", m["description"])


class Rotulo(unittest.TestCase):
    def test_tarefa_e_rodada(self):
        self.assertEqual(w.partes_do_rotulo("T148 revisar 2", "Revisar"), ("T148", 2))
        self.assertEqual(w.partes_do_rotulo("T148 corrigir", "Corrigir"), ("T148", None))
        self.assertEqual(w.partes_do_rotulo("painel-workflows fazer", "Fazer"), ("painel-workflows", None))
        self.assertEqual(w.partes_do_rotulo("T3a fazer 1", "Fazer"), ("T3a", 1))
        self.assertEqual(w.partes_do_rotulo("sem etapa nenhuma", "Fazer"), ("sem etapa nenhuma", None))
        self.assertEqual(w.partes_do_rotulo("", ""), ("", None))


class Andamento(unittest.TestCase):
    def ent(self):
        from analisadores import parse_journal
        return parse_journal(JOURNAL)

    def test_etapa_atual_e_contagem_por_fase(self):
        r = w.andamento(self.ent(), ["Fazer", "Revisar", "Corrigir"], ARGS["tarefas"], {"a2", "a4"})
        por = {f["titulo"]: f for f in r["fases"]}
        self.assertEqual((por["Fazer"]["iniciados"], por["Fazer"]["terminados"], por["Fazer"]["estado"]), (2, 1, "atual"))
        self.assertEqual((por["Revisar"]["iniciados"], por["Revisar"]["terminados"], por["Revisar"]["estado"]), (1, 1, "feita"))
        self.assertEqual(por["Corrigir"]["estado"], "atual")
        self.assertEqual(r["fase_atual"], "Fazer")  # a primeira etapa com agente rodando

    def test_fase_que_nao_comecou_falta(self):
        r = w.andamento([], ["Fazer", "Revisar"], [], set())
        self.assertEqual([f["estado"] for f in r["fases"]], ["falta", "falta"])
        self.assertIsNone(r["fase_atual"])

    def test_etapa_fora_do_meta_entra_no_fim(self):
        ents = [{"agentId": "x", "label": "T1 sintese", "fase": "Síntese", "status": "rodando", "resumo": ""}]
        r = w.andamento(ents, ["Fazer"], [], {"x"})
        self.assertEqual([f["titulo"] for f in r["fases"]], ["Fazer", "Síntese"])

    def test_tarefas(self):
        r = w.andamento(self.ent(), ["Fazer", "Revisar", "Corrigir"], ARGS["tarefas"], {"a2", "a4"})
        t = {x["id"]: x for x in r["tarefas"]}
        self.assertEqual(list(t), ["T1", "T2", "T3"])  # ordem do args
        self.assertEqual((t["T1"]["estado"], t["T1"]["etapa"], t["T1"]["agentes"], t["T1"]["feitos"]), ("rodando", "Corrigir", 3, 2))
        self.assertEqual(t["T1"]["rodada"], 1)  # última rodada vista: a revisão 1
        self.assertEqual((t["T2"]["estado"], t["T2"]["etapa"], t["T2"]["passos"]), ("rodando", "Fazer", 2))
        self.assertEqual((t["T3"]["estado"], t["T3"]["etapa"], t["T3"]["agentes"], t["T3"]["passos"]), ("aguardando", "", 0, 1))
        self.assertEqual(t["T1"]["ultimo"], "reprovado")

    def test_entre_etapas(self):
        r = w.andamento(self.ent(), ["Fazer", "Revisar", "Corrigir"], ARGS["tarefas"], set())  # ninguém vivo
        t = {x["id"]: x for x in r["tarefas"]}
        self.assertEqual((t["T1"]["estado"], t["T3"]["estado"]), ("entre passos", "aguardando"))
        self.assertIsNone(r["fase_atual"])

    def test_sem_args_agrupa_pelo_rotulo(self):
        r = w.andamento(self.ent(), ["Fazer", "Revisar", "Corrigir"], [], {"a2"})
        self.assertEqual([x["id"] for x in r["tarefas"]], ["T1", "T2"])

    def test_passo_do_args_casa_pelo_nome_do_passo(self):
        ents = [{"agentId": "p", "label": "T2b fazer", "fase": "Fazer", "status": "rodando", "resumo": ""}]
        r = w.andamento(ents, ["Fazer"], ARGS["tarefas"], {"p"})
        t = {x["id"]: x for x in r["tarefas"]}
        self.assertEqual((t["T2"]["agentes"], t["T2"]["estado"]), (1, "rodando"))
        self.assertNotIn("T2b", t)


class Lancamentos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p = os.path.join(self.tmp, "s.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def uso(self, tid, **inp):
        return json.dumps({"type": "assistant", "timestamp": "2026-11-01T10:00:00Z", "message": {"content": [
            {"type": "tool_use", "id": tid, "name": "Workflow", "input": inp}]}}) + "\n"

    def res(self, tid, run):
        return json.dumps({"type": "user", "timestamp": "2026-11-01T10:00:02Z", "message": {"content": [
            {"type": "tool_result", "tool_use_id": tid, "content": f"Workflow launched.\nRun ID: {run}\nTask ID: tx"}]}}) + "\n"

    def test_script_path_e_args_em_texto(self):
        with open(self.p, "w") as f:
            f.write(self.uso("u1", scriptPath="/x/fazer.js", args=json.dumps(
                {"tarefas": [{"id": "T9", "modelo": "sonnet", "effort": "high", "brief": {"tarefa": "segredo token=abc123xyz"},
                              "passos": [{"nome": "T9a", "brief": "x"}]}]})) + self.res("u1", "wf_aaa-111"))
        est = w.ler_lancamentos(None, self.p)
        r = est["runs"]["wf_aaa-111"]
        self.assertEqual(r["script_path"], "/x/fazer.js")
        self.assertEqual(r["tarefas"], [{"id": "T9", "passos": ["T9a"], "modelo": "sonnet", "effort": "high"}])
        self.assertNotIn("brief", json.dumps(est))
        self.assertGreater(r["inicio"], 0)

    def test_script_inline_vira_meta_e_args_objeto(self):
        with open(self.p, "w") as f:
            f.write(self.uso("u1", script="export const meta = {name: 'inline', phases: [{title: 'A'}]}\nlogo()", args={"tarefas": [{"id": "X"}]})
                    + self.res("u1", "wf_bbb-222"))
        r = w.ler_lancamentos(None, self.p)["runs"]["wf_bbb-222"]
        self.assertEqual(r["meta"]["name"], "inline")
        self.assertEqual([t["id"] for t in r["tarefas"]], ["X"])

    def test_sem_resultado_nao_vira_run_e_incremental(self):
        with open(self.p, "w") as f:
            f.write(self.uso("u1", scriptPath="/x.js"))
        est = w.ler_lancamentos(None, self.p)
        self.assertEqual(est["runs"], {})
        with open(self.p, "a") as f:
            f.write(self.res("u1", "wf_ccc-333"))
        self.assertIn("wf_ccc-333", w.ler_lancamentos(est, self.p)["runs"])

    def test_linha_com_texto_parecido_e_args_quebrado(self):
        with open(self.p, "w") as f:
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Run ID: wf_zzz-999"}]}}) + "\n"
                    + self.uso("u1", scriptPath="/x.js", args="{quebrado") + self.res("u1", "wf_ddd-444"))
        est = w.ler_lancamentos(None, self.p)
        self.assertEqual(list(est["runs"]), ["wf_ddd-444"])
        self.assertEqual(est["runs"]["wf_ddd-444"]["tarefas"], [])


class Terminado(unittest.TestCase):
    def test_do_json(self):
        info = {"workflowName": "a4-e-t134", "summary": "A4 e T134: fazer", "status": "completed", "startTime": 1793460715899,
                "durationMs": 805936, "agentCount": 8, "totalTokens": 795152,
                "phases": [{"title": "Fazer"}, {"title": "Revisar"}]}
        r = w.terminado("wf_04583c72-3d0", info, 1793461521.0)
        self.assertEqual((r["id"], r["nome"], r["status"], r["duracao"], r["agentes"], r["tokens"]),
                         ("wf_04583c72-3d0", "a4-e-t134", "completed", 805.936, 8, 795152))
        self.assertEqual(r["fases"], ["Fazer", "Revisar"])
        self.assertEqual(r["inicio"], 1793460715.899)
        self.assertEqual(r["fim"], 1793461521.0)

    def test_json_pobre(self):
        r = w.terminado("wf_x", {}, 5.0)
        self.assertEqual((r["nome"], r["status"], r["duracao"], r["tokens"], r["fases"]), ("wf_x", "?", None, 0, []))

    def test_mascara_resumo(self):
        r = w.terminado("wf_x", {"summary": "usa senha=abc123xyz"}, 1.0)
        self.assertNotIn("abc123xyz", r["resumo"])


class Coletar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sd = os.path.join(self.tmp, "sess")
        wf = os.path.join(self.sd, "subagents", "workflows", "wf_run-111")
        os.makedirs(wf)
        os.makedirs(os.path.join(self.sd, "workflows", "scripts"))
        with open(os.path.join(wf, "journal.jsonl"), "w") as f:
            f.write(JOURNAL)
        with open(os.path.join(self.sd, "workflows", "scripts", "fazer-wf_run-111.js"), "w") as f:
            f.write(SCRIPT)
        for n, (nome, ts) in enumerate([("velho", 100), ("meio", 200), ("novo", 300), ("novissimo", 400)]):
            p = os.path.join(self.sd, "workflows", f"wf_t{n}.json")
            with open(p, "w") as f:
                json.dump({"workflowName": nome, "status": "completed", "durationMs": 1000}, f)
            os.utime(p, (ts, ts))
        self.wfs = [{"id": "wf_run-111", "nome": "x", "rodando": True, "status": "rodando"}]
        self.ags = [{"id": "a2", "rotulo": "T2 fazer", "modelo": "claude-sonnet-5-5", "effort": "high", "workflow": "wf_run-111",
                     "fase": "Fazer", "ativo": True, "inicio": 1000.0},
                    {"id": "a4", "rotulo": "T1 corrigir", "modelo": "claude-opus-5-5", "effort": "xhigh", "workflow": "wf_run-111",
                     "fase": "Corrigir", "ativo": True, "inicio": 1100.0},
                    {"id": "a1", "rotulo": "T1 fazer", "modelo": "x", "effort": "", "workflow": "wf_run-111", "fase": "Fazer", "ativo": False, "inicio": 900.0}]
        self.lanc = {"runs": {"wf_run-111": {"meta": None, "script_path": None, "tarefas": ARGS["tarefas"], "inicio": 950.0}}}
        self.con = {"workflows": [{"id": "wf_run-111", "tokens": 12345, "segundos": 600}]}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def coleta(self, **kw):
        return w.coletar(self.sd, self.wfs, self.ags, self.lanc, self.con, 1200.0, **kw)

    def test_rodando_completo(self):
        r = self.coleta()["rodando"]
        self.assertEqual(len(r), 1)
        q = r[0]
        self.assertEqual((q["id"], q["nome"], q["descricao"]), ("wf_run-111", "fazer-revisar-corrigir", "Cada tarefa: um agente faz, outro revisa"))
        self.assertEqual([f["titulo"] for f in q["fases"]], ["Fazer", "Revisar", "Corrigir"])
        self.assertEqual(q["fase_atual"], "Fazer")
        self.assertEqual((q["tokens"], q["segundos"], q["desde"]), (12345, 250.0, 950.0))
        self.assertEqual((q["agentes_total"], q["agentes_feitos"]), (4, 2))
        self.assertEqual([(x["rotulo"], x["modelo"], x["effort"]) for x in q["agentes"]],
                         [("T2 fazer", "claude-sonnet-5-5", "high"), ("T1 corrigir", "claude-opus-5-5", "xhigh")])
        self.assertEqual([t["id"] for t in q["tarefas"]], ["T1", "T2", "T3"])

    def test_sem_script_so_o_runid(self):
        os.unlink(os.path.join(self.sd, "workflows", "scripts", "fazer-wf_run-111.js"))
        q = self.coleta()["rodando"][0]
        self.assertEqual((q["nome"], q["descricao"]), ("wf_run-111", ""))
        self.assertEqual([f["titulo"] for f in q["fases"]], ["Fazer", "Revisar", "Corrigir"])  # da própria journal

    def test_script_path_do_lancamento(self):
        caminho = os.path.join(self.tmp, "meu.js")
        with open(caminho, "w") as f:
            f.write("export const meta = {name: 'do-caminho', phases: [{title: 'Z'}]}")
        os.unlink(os.path.join(self.sd, "workflows", "scripts", "fazer-wf_run-111.js"))
        self.lanc["runs"]["wf_run-111"]["script_path"] = caminho
        q = self.coleta(projeto=self.tmp)["rodando"][0]
        self.assertEqual(q["nome"], "do-caminho")
        self.assertEqual([f["titulo"] for f in q["fases"]], ["Z", "Fazer", "Revisar", "Corrigir"])

    def test_recentes_sao_os_3_ultimos_sem_os_rodando(self):
        r = self.coleta()["recentes"]
        self.assertEqual([x["nome"] for x in r], ["novissimo", "novo", "meio"])

    def test_script_path_fora_das_pastas_permitidas_e_ignorado(self):
        caminho = os.path.join(self.tmp, "meu.js")
        with open(caminho, "w") as f:
            f.write("export const meta = {name: 'do-caminho', phases: [{title: 'Z'}]}")
        os.unlink(os.path.join(self.sd, "workflows", "scripts", "fazer-wf_run-111.js"))
        self.lanc["runs"]["wf_run-111"]["script_path"] = caminho
        self.assertEqual(self.coleta()["rodando"][0]["nome"], "wf_run-111")  # projeto não é o tmp
        os.symlink(caminho, os.path.join(self.tmp, "ln.js"))
        self.assertEqual(self.coleta(projeto=os.path.join(self.tmp, "outra"))["rodando"][0]["nome"], "wf_run-111")

    def test_rodando_sem_sinal_fica_com_o_aviso(self):
        for x in self.ags:
            x["ativo"], x["ultimo_sinal"] = False, 1200.0 - 600
        r = self.coleta()["rodando"]
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["sem_sinal"], 600.0)

    def test_com_sinal_recente_nao_tem_aviso(self):
        self.ags[0]["ultimo_sinal"] = 1190.0
        self.assertIsNone(self.coleta()["rodando"][0]["sem_sinal"])

    def test_parado_depois_de_2h_vai_para_terminados(self):
        for x in self.ags:
            x["ativo"], x["ultimo_sinal"] = False, 1000.0
        r = w.coletar(self.sd, self.wfs, self.ags, self.lanc, self.con, 1000.0 + 7201)
        self.assertEqual(r["rodando"], [])
        self.assertEqual(r["recentes"][0]["id"], "wf_run-111")
        self.assertEqual(r["recentes"][0]["status"], "killed")

    def test_workflow_que_terminou_nao_esta_em_rodando(self):
        with open(os.path.join(self.sd, "workflows", "wf_run-111.json"), "w") as f:
            json.dump({"workflowName": "fim", "status": "completed"}, f)
        r = self.coleta()
        self.assertEqual(r["rodando"], [])

    def test_vazio(self):
        r = w.coletar(self.sd, [], [], None, None, 5.0)
        self.assertEqual(r["rodando"], [])
        self.assertEqual(len(r["recentes"]), 3)

    def test_nada_sensivel_sai(self):
        with open(os.path.join(self.sd, "subagents", "workflows", "wf_run-111", "journal.jsonl"), "a") as f:
            f.write(j(type="started", agentId="a9", label="T7 fazer senha=abc123xyz", phase="Fazer"))
        self.ags.append({"id": "a9", "rotulo": "T7 fazer senha=abc123xyz", "modelo": "m", "effort": "", "workflow": "wf_run-111",
                         "fase": "Fazer", "ativo": True, "inicio": 1.0})
        self.assertNotIn("abc123xyz", json.dumps(self.coleta()))


class Planejados(unittest.TestCase):
    def test_soma_os_passos_do_args_e_ignora_run_sem_tarefas(self):
        lanc = {"runs": {"wf_a": {"tarefas": [{"id": "T1", "passos": ["fazer", "revisar"]}, {"id": "T2", "passos": []}]},
                         "wf_b": {"tarefas": []}, "wf_c": {}}}
        self.assertEqual(w.planejados(lanc), {"wf_a": 3})  # tarefa sem passos conta 1, como em andamento()
        self.assertEqual(w.planejados(None), {})


if __name__ == "__main__":
    unittest.main()
