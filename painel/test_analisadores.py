import json
import unittest

import analisadores as a

TASKS = """# Tarefas

## T22 · Arrumar o histórico
- **Origem:** x
- **Estado:** **feita e na `main`** (PR #31, 29/10).

### T146 · Base das leis
- **Estado:** em andamento, branch `feat/t146-leis`.

### T161 · Prazo estadual
- **Estado:** registrada.

### T164 · Teste de tela
- **Estado:** esperando o escritório.

### T165 · Respostas
- **Estado:** NA `dev` (31/10): migration aplicada.

### T148 a T150 · Pegar mais defeito
- **Estado:**
  em implementação, três frentes.

### T167 · Skill publicar
- **Estado:** registrada; depois que a documentação do fluxo entrar na `dev`.

### T159 · Fluxo documentado
- **Estado:** em andamento, na branch `docs/x`; falta juntar na `dev`.

### T171 · Arquivo
- **Estado:** registrada; mexer no arquivo no ar.

### T172 · Negada
- **Estado:** não feita ainda.

### T170 · Sem estado
- **Origem:** nada ainda
"""

DUVIDAS = """# Dúvidas

## Permissões (ações)

### P-1. Aplicar migration em produção?
- texto
- **Resposta (dono):** sim

## Decisões

### D-10. Sistema externo (T125·O3)
- ainda sem resposta

### D-11. Integração
- **Pergunta:** x

### D-12. Fechada
- **Resposta:** feito

## Avisar a outra frente (código dela mexido)

- **C5 (na `dev`):** ler-anexo.tsx ganhou campo.
  continuação da linha.
- **E4 (Cofre):** executor do job.
"""

JOURNAL = "\n".join(json.dumps(x) for x in [
    {"type": "launched"},
    {"type": "started", "agentId": "a1", "label": "T166 fazer", "phase": "Fazer"},
    {"type": "started", "agentId": "a2", "label": "T167 fazer", "phase": "Fazer"},
    {"type": "result", "agentId": "a2", "result": {"status": "parcial"}},
    {"type": "started", "agentId": "a3", "label": "T167 revisar", "phase": "Revisar"},
    {"type": "result", "agentId": "a3", "result": {"veredito": "aprovado"}},
    "lixo que não é json",
][:-1]) + "\nlixo que não é json\n"

CADEIA = """== t162 saida=0
sincronizar: banco local em dia
t162: na dev (7fa2c556 cho)
== c2c saida=1
FALHOU  painel: testes de tela
PAREI em c2c
"""

BATERIA = """::: scripts do CI (unittest)
OK (skipped=29)
::: painel: testes de tela (Playwright, ambiente local)
  ✓    1 [chromium] › e2e/a.spec.ts:1:1 › um (1.0s)
  ✓    2 [chromium] › e2e/a.spec.ts:2:1 › dois (1.0s)
  ✘    3 [chromium] › e2e/b.spec.ts:2:1 › tres (1.0s)
  ✓    4 [chromium] › e2e/a.spec.ts:2:1 › quatro (1.0s)
"""

BATERIA_FIM = """::: testes SQL (banco novo)
=== resumo (base: dev) ===
OK  scripts do CI (unittest)
PULADO  banco-em-dia (sem chave)
FALHOU  painel: testes de tela (Playwright, ambiente local)
FALHOU: corrija antes de juntar na dev
"""


class TestTasks(unittest.TestCase):
    def setUp(self):
        self.t = {x["id"]: x for x in a.parse_tasks(TASKS)}

    def test_estados(self):
        self.assertEqual(self.t[22]["estado"], "concluida")
        self.assertEqual(self.t[146]["estado"], "andando")
        self.assertEqual(self.t[161]["estado"], "fila")
        self.assertEqual(self.t[164]["estado"], "bloqueada")
        self.assertEqual(self.t[165]["estado"], "concluida")
        self.assertEqual(self.t[170]["estado"], "desconhecido")

    def test_palavra_concluida_no_meio_nao_vence(self):
        self.assertEqual(self.t[167]["estado"], "fila")
        self.assertEqual(self.t[159]["estado"], "andando")
        self.assertEqual(self.t[171]["estado"], "fila")
        self.assertNotEqual(self.t[172]["estado"], "concluida")

    def test_titulo_e_texto(self):
        self.assertEqual(self.t[146]["titulo"], "Base das leis")
        self.assertIn("feat/t146-leis", self.t[146]["estado_texto"])

    def test_estado_na_linha_seguinte_e_faixa(self):
        for n in (148, 149, 150):
            self.assertEqual(self.t[n]["estado"], "andando")


class TestDuvidas(unittest.TestCase):
    def test_abertas(self):
        ab = a.parse_duvidas(DUVIDAS)
        self.assertEqual([d["id"] for d in ab], ["D-10", "D-11"])
        self.assertTrue(ab[0]["titulo"].startswith("Sistema externo"))

    def test_avisos(self):
        av = a.parse_avisos(DUVIDAS)
        self.assertEqual(len(av), 2)
        self.assertIn("ler-anexo.tsx", av[0])
        self.assertIn("continuação", av[0])


class TestJournal(unittest.TestCase):
    def test_rodando_e_terminado(self):
        j = {x["agentId"]: x for x in a.parse_journal(JOURNAL)}
        self.assertEqual(j["a1"]["status"], "rodando")
        self.assertEqual(j["a2"]["status"], "terminado")
        self.assertEqual(j["a2"]["resumo"], "parcial")
        self.assertEqual(j["a3"]["resumo"], "aprovado")
        self.assertEqual(j["a1"]["fase"], "Fazer")


class TestCadeia(unittest.TestCase):
    def test_cadeia(self):
        c = a.parse_cadeia(CADEIA)
        self.assertEqual(c["parou"], "c2c")
        self.assertEqual(c["na_dev"], [{"wt": "t162", "sha": "7fa2c556"}])
        self.assertEqual(c["resultados"], [{"wt": "t162", "saida": 0}, {"wt": "c2c", "saida": 1}])


class TestBateria(unittest.TestCase):
    def test_em_andamento(self):
        b = a.parse_bateria(BATERIA)
        self.assertEqual(b["passo"], "painel: testes de tela (Playwright, ambiente local)")
        self.assertEqual(b["tela_feitos"], 4)
        self.assertEqual(b["tela_falhas"], 1)
        self.assertFalse(b["terminou"])

    def test_terminada(self):
        b = a.parse_bateria(BATERIA_FIM)
        self.assertTrue(b["terminou"])
        self.assertEqual([r["status"] for r in b["resumo"]], ["OK", "PULADO", "FALHOU"])
        self.assertEqual(b["resumo"][2]["nome"], "painel: testes de tela (Playwright, ambiente local)")


class TestRamo(unittest.TestCase):
    def test_numero_da_tarefa(self):
        self.assertEqual(a.numero_da_tarefa("feat/t146-leis"), 146)
        self.assertEqual(a.numero_da_tarefa("/x/wt/t169"), 169)
        self.assertIsNone(a.numero_da_tarefa("feat/c7-buscar"))

    def test_letra_no_fim(self):
        self.assertEqual(a.numero_da_tarefa("t146i"), 146)
        self.assertEqual(a.numero_da_tarefa("/x/wt/t145b"), 145)
        self.assertEqual(a.numero_da_tarefa("feat/t145c-algo"), 145)

    def test_melhor_worktree(self):
        w = [{"nome": "t145", "a_frente": 0}, {"nome": "t145b", "a_frente": 3}, {"nome": "t145c", "a_frente": 1}]
        self.assertEqual(a.melhor_worktree(w, None)["nome"], "t145b")
        self.assertEqual(a.melhor_worktree(w, "t145c")["nome"], "t145c")
        self.assertIsNone(a.melhor_worktree([], None))

    def test_melhor_worktree_considera_nao_commitado(self):
        w = [{"nome": "t9", "a_frente": 0, "mudancas_nao_commitadas": 0},
             {"nome": "t9b", "a_frente": 0, "mudancas_nao_commitadas": 4}]
        self.assertEqual(a.melhor_worktree(w, None)["nome"], "t9b")


class TestHost(unittest.TestCase):
    def test_host(self):
        self.assertTrue(a.host_permitido("127.0.0.1:8765", 8765))
        self.assertTrue(a.host_permitido("localhost:8765", 8765))
        self.assertFalse(a.host_permitido("evil.com:8765", 8765))
        self.assertFalse(a.host_permitido("127.0.0.1.evil.com:8765", 8765))
        self.assertFalse(a.host_permitido(None, 8765))


class TestGitSemTrava(unittest.TestCase):
    def test_status_nao_pega_index_lock(self):
        import fontes
        chamadas = []

        def falso(args, cwd=None, timeout=8):
            chamadas.append(args)
            if args[:3] == ["git", "worktree", "list"] or "worktree" in args:
                return "worktree /w/t1\nHEAD abc\nbranch refs/heads/feat/t1-x\n"
            return ""

        orig = fontes._cmd
        fontes._cmd = falso
        try:
            fontes.git_worktrees({"projeto": "/p", "worktrees": "/w"})
        finally:
            fontes._cmd = orig
        st = [c for c in chamadas if "status" in c]
        self.assertTrue(st)
        self.assertTrue(all("--no-optional-locks" in c for c in st))


class TestWorktreesDoGit(unittest.TestCase):
    def _rodar(self, porcelain, merges):
        import fontes

        def falso(args, cwd=None, timeout=8):
            if args[:3] == ["git", "worktree", "list"]:
                return porcelain
            if "--merges" in args:
                return merges
            if "rev-list" in args:
                return "0\n"
            return ""

        orig = fontes._cmd
        fontes._cmd = falso
        try:
            return fontes.git_worktrees({"projeto": "/p", "worktrees": "/w"})
        finally:
            fontes._cmd = orig

    def test_na_dev_e_so_head_nos_merges(self):
        r = self._rodar("worktree /w/t1\nHEAD abc\nbranch refs/heads/feat/t1-x\n\nworktree /w/t2\nHEAD def\nbranch refs/heads/feat/t2\n",
                        "p1 abc\n")
        self.assertEqual({w["nome"]: w["na_dev"] for w in r}, {"t1": True, "t2": False})

    def test_pula_worktree_sem_head(self):
        r = self._rodar("worktree /w/t3\nbare\n\nworktree /w/t4\nHEAD abc\nbranch refs/heads/t4\n", "")
        self.assertEqual([w["nome"] for w in r], ["t4"])


class TestTarefaComWorkflow(unittest.TestCase):
    def test_registrada_com_workflow_rodando_e_andando_com_fracao(self):
        import os
        import tempfile
        import fontes
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "TASKS.md"), "w") as f:
                f.write("### T200 · Nova\n- **Estado:** registrada.\n\n### T201 · Sem estado\n- **Origem:** x\n")
            wfs = [{"id": "wf_1", "nome": "w", "rodando": True, "feitos": 3, "agentes": 4, "tarefas": [200, 201]}]
            bat = {"rodando": None, "fila": []}
            r = {t["id"]: t for t in fontes.tarefas({"projeto": d, "leva_a_partir_de": 1}, [], wfs, bat)}
        self.assertEqual((r[200]["estado"], r[200]["percentual"]), ("andando", 75))
        self.assertEqual((r[201]["estado"], r[201]["percentual"]), ("andando", 75))

    def test_fracao_usa_o_total_planejado_quando_existe(self):
        import os
        import tempfile
        import fontes
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "TASKS.md"), "w") as f:
                f.write("### T200 · Nova\n- **Estado:** registrada.\n")
            # 4 agentes lançados, 3 prontos, 8 passos planejados: 3/8, não 3/4 (que cairia a cada passo novo)
            wfs = [{"id": "wf_1", "nome": "w", "rodando": True, "feitos": 3, "agentes": 4, "planejados": 8, "tarefas": [200]}]
            r = fontes.tarefas({"projeto": d, "leva_a_partir_de": 1}, [], wfs, {"rodando": None, "fila": []})
        self.assertEqual((r[0]["wf_frac"], r[0]["percentual"]), ((3, 8), 38))


class TestPercentual(unittest.TestCase):
    def test_percentuais(self):
        p = a.percentual
        self.assertEqual(p("concluida"), 100)
        self.assertEqual(p("fila"), 0)
        self.assertEqual(p("andando"), 40)
        self.assertEqual(p("andando", wt={"a_frente": 2, "na_dev": False}), 85)
        self.assertEqual(p("andando", wt={"a_frente": 2, "na_dev": False}, bateria_rodando=True), 90)
        self.assertEqual(p("andando", workflow=(3, 4)), 75)

    def test_workflow_antes_da_branch_a_frente(self):
        p = a.percentual
        self.assertEqual(p("andando", wt={"a_frente": 2, "na_dev": False}, workflow=(1, 4)), 25)
        self.assertEqual(p("andando", wt={"a_frente": 2, "na_dev": False}, workflow=(1, 4), bateria_rodando=True), 90)

    def test_bloqueada_fica_a_parte(self):
        self.assertEqual(a.percentual("bloqueada"), 0)
        self.assertEqual(a.percentual("bloqueada", wt={"a_frente": 2, "na_dev": False}), 0)


class TestWorkflowRetomado(unittest.TestCase):
    def test_status_do_json_velho_e_ignorado(self):
        f = a.status_workflow
        self.assertIsNone(f("killed", 200, 100))   # journal mais novo: foi retomado
        self.assertEqual(f("killed", 100, 200), "killed")
        self.assertEqual(f("completed", 100, 200), "completed")
        self.assertIsNone(f(None, 100, 200))


class TestEstadoEfetivo(unittest.TestCase):
    def test_na_dev_limpo_vira_concluida(self):
        e = a.estado_efetivo
        limpo = {"na_dev": True, "mudancas_nao_commitadas": 0, "a_frente": 0}
        self.assertEqual(e("andando", limpo, False), "concluida")
        self.assertEqual(e("desconhecido", limpo, False), "concluida")
        self.assertEqual(e("fila", limpo, False), "concluida")

    def test_na_dev_mas_sujo_ou_com_workflow_continua_andando(self):
        e = a.estado_efetivo
        sujo = {"na_dev": True, "mudancas_nao_commitadas": 12, "a_frente": 0}
        self.assertEqual(e("andando", sujo, False), "andando")
        self.assertEqual(e("desconhecido", sujo, False), "andando")
        limpo = {"na_dev": True, "mudancas_nao_commitadas": 0, "a_frente": 0}
        self.assertEqual(e("andando", limpo, True), "andando")

    def test_bloqueada_e_sem_worktree_ficam_como_estao(self):
        e = a.estado_efetivo
        self.assertEqual(e("bloqueada", {"na_dev": True, "mudancas_nao_commitadas": 0}, False), "bloqueada")
        self.assertEqual(e("fila", None, False), "fila")
        self.assertEqual(e("fila", {"na_dev": False, "a_frente": 2}, False), "andando")

    def test_percentual_na_dev_sujo_nao_e_cem(self):
        sujo = {"na_dev": True, "mudancas_nao_commitadas": 12, "a_frente": 0}
        self.assertLess(a.percentual("andando", wt=sujo), 100)
        self.assertLess(a.percentual("andando", wt={"na_dev": True, "a_frente": 0}, workflow=(1, 4)), 100)


DUVIDAS_OPCOES = """## Decisões

### D-29. Ordem de publicação
- **Situação:** a skill diz uma coisa
  e a memória diz outra.
- **Opções:** (a) **recomendada:** a ordem de 30/10 (PR, CI, migrations, merge). Atende; (b) a da skill, aceitando
  migration sem CI.
- **Enquanto isso:** segue a (a).

### D-11. Integração
- **Situação:** sem doc.
- **Opções:** (a) pedir a documentação (recomendado: não expõe token); (b) chamar a API com token.

### D-35. Permissões
- **Equipes:** quem não é admin só reativa.
- **Desativar conta:** mesma regra.

### P-2. Aplicar migrations
- **Situação:** escritas e testadas.
"""


class TestDuvidasDetalhe(unittest.TestCase):
    def setUp(self):
        self.d = {x["id"]: x for x in a.parse_duvidas(DUVIDAS_OPCOES)}

    def test_situacao(self):
        self.assertEqual(self.d["D-29"]["situacao"], "a skill diz uma coisa e a memória diz outra.")
        self.assertIn("quem não é admin", self.d["D-35"]["situacao"])  # sem Situação: o corpo

    def test_opcoes_e_recomendada(self):
        o = self.d["D-29"]["opcoes"]
        self.assertEqual([x["letra"] for x in o], ["a", "b"])
        self.assertTrue(o[0]["recomendada"])
        self.assertFalse(o[1]["recomendada"])
        self.assertTrue(o[0]["texto"].startswith("a ordem de 30/10"))
        self.assertNotIn("**", o[0]["texto"])
        self.assertIn("migration sem CI", o[1]["texto"])
        o = self.d["D-11"]["opcoes"]
        self.assertTrue(o[0]["recomendada"])
        self.assertEqual(self.d["P-2"]["opcoes"], [])

    def test_recomendado_dito_depois(self):
        (d,) = a.parse_duvidas("### D-32. X\n- Opções: (a) deixar; (b) escapar `<`. Recomendado: (a). A regra vale.\n")
        self.assertEqual([o["recomendada"] for o in d["opcoes"]], [True, False])
        self.assertNotIn("Recomendado", d["opcoes"][1]["texto"])


class TestRede(unittest.TestCase):
    SAIDA = """1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever
2: enp1s0    inet 192.168.0.231/24 brd 192.168.0.255 scope global enp1s0\\       valid_lft 1
3: wlp2s0    inet 192.168.0.213/24 brd 192.168.0.255 scope global wlp2s0\\       valid_lft 1
4: br-3a7e05d13370    inet 172.21.0.1/16 brd 172.21.255.255 scope global br-3a7e\\       valid_lft 1
8: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\\       valid_lft 1
9: eth0    inet 10.0.0.5/8 scope global eth0
10: wlan0    inet 10.1.0.5/8 scope global wlan0
"""

    def test_ips_da_rede(self):
        self.assertEqual(a.ips_da_rede(self.SAIDA), ["192.168.0.231", "192.168.0.213", "10.0.0.5", "10.1.0.5"])

    def test_host_com_nomes_da_maquina(self):
        nomes = ["192.168.0.231", "fedora"]
        self.assertTrue(a.host_permitido("192.168.0.231:8791", 8791, nomes))
        self.assertTrue(a.host_permitido("fedora:8791", 8791, nomes))
        self.assertTrue(a.host_permitido("127.0.0.1:8791", 8791, nomes))
        self.assertFalse(a.host_permitido("192.168.0.99:8791", 8791, nomes))
        self.assertFalse(a.host_permitido("192.168.0.231:9999", 8791, nomes))
        self.assertFalse(a.host_permitido("evil.com:8791", 8791, nomes))


class TestAcesso(unittest.TestCase):
    CH = "k" * 32

    def test_local_sem_chave(self):
        self.assertTrue(a.acesso_liberado("127.0.0.1", None, self.CH))

    def test_outro_ip_exige_cookie(self):
        self.assertFalse(a.acesso_liberado("192.168.0.50", None, self.CH))
        self.assertFalse(a.acesso_liberado("192.168.0.50", "painel_chave=errada", self.CH))
        self.assertFalse(a.acesso_liberado("192.168.0.50", "painel_chave=ção", self.CH))
        self.assertFalse(a.acesso_liberado("192.168.0.50", "lixo;;=\\x00", self.CH))
        self.assertTrue(a.acesso_liberado("192.168.0.50", f"x=1; painel_chave={self.CH}", self.CH))

    def test_outro_cookie_estranho_nao_derruba_a_chave(self):
        # cookie não separa porta: outro app no mesmo IP pode deixar cookie com JSON/espaço
        self.assertTrue(a.acesso_liberado("192.168.0.50", 'sb-x={"a":1}; painel_chave=' + self.CH, self.CH))
        self.assertTrue(a.acesso_liberado("192.168.0.50", "x=y z; painel_chave=" + self.CH, self.CH))
        self.assertFalse(a.acesso_liberado("192.168.0.50", "outro_painel_chave=" + self.CH, self.CH))

    def test_chave_vazia_nunca_libera(self):
        self.assertFalse(a.acesso_liberado("192.168.0.50", "painel_chave=", ""))

    def test_chave_confere(self):
        self.assertTrue(a.chave_confere(self.CH, self.CH))
        self.assertFalse(a.chave_confere("x", self.CH))
        self.assertFalse(a.chave_confere(None, self.CH))
        self.assertFalse(a.chave_confere("ção", self.CH))


class TestValidarResposta(unittest.TestCase):
    AB = [{"id": "D-29", "titulo": "Ordem", "opcoes": [{"letra": "a", "texto": "x", "recomendada": True},
                                                      {"letra": "b", "texto": "y", "recomendada": False}]},
          {"id": "P-2", "titulo": "Migrations", "opcoes": []}]

    def ok(self, corpo):
        erro, limpo = a.validar_resposta(corpo, self.AB)
        self.assertIsNone(erro, erro)
        return limpo

    def falha(self, corpo):
        erro, _ = a.validar_resposta(corpo, self.AB)
        self.assertTrue(erro)

    def test_validas(self):
        r = self.ok({"id": "D-29", "opcao": "a", "texto": "pode seguir"})
        self.assertEqual((r["id"], r["opcao"], r["opcao_texto"], r["texto"], r["titulo"]), ("D-29", "a", "x", "pode seguir", "Ordem"))
        self.assertIsNone(self.ok({"id": "P-2", "texto": "sim"})["opcao"])
        self.assertEqual(self.ok({"id": "D-29", "texto": "linha 1\nlinha 2"})["texto"], "linha 1\nlinha 2")
        self.ok({"id": "D-29", "texto": "ok \U0001F468\u200d\U0001F469\u200d\U0001F467"})  # emoji composto (ZWJ) do celular

    def test_invalidas(self):
        self.falha({"id": "D-99", "texto": "x"})            # não é dúvida aberta
        self.falha({"id": "D-29", "opcao": "c", "texto": "x"})
        self.falha({"id": "P-2", "opcao": "a", "texto": "x"})
        self.falha({"id": "D-29", "texto": "x" * 2001})
        self.falha({"id": "D-29", "texto": "a\x1bb"})
        self.falha({"id": "D-29", "texto": "a‮b"})       # controle de direção (invisível)
        self.falha({"id": "D-29", "texto": "   "})            # nem opção nem texto
        self.falha({"id": "D-29", "texto": 5})
        self.falha({"id": ["D-29"], "texto": "x"})
        self.falha(["D-29"])
        self.assertIsNone(a.validar_resposta({"id": "D-29", "texto": "x" * 2000}, self.AB)[0])


class TestDuvidasIdLetraEOpcoes(unittest.TestCase):
    MD = """## Decisões

### D-35. Permissões
- **Resposta (1º/11):** confirmo.

### D-35b. Igualar todos
- **Situação:** só para conferir.
- Foi feito assim: (a) a tela mostra o botão; (b) o banco aceita; (c) o resto avisa.

### D-35c. Aviso do pulado
- **Resposta (2/11, pelo painel):** ok.
- **Decidido pela sessão (2/11):** sim.

### D-44. Escolha de verdade
- **Situação:** duas saídas.
- **Opções:** (a) uma, recomendada; (b) outra.

### D-45. Só decidido
- **Decidido pela sessão (2/11):** fica assim, sem resposta do usuário.

### D-46. Lista de opções
- (a) primeira
- (b) segunda (recomendado)
"""

    def setUp(self):
        self.d = {x["id"]: x for x in a.parse_duvidas(self.MD)}

    def test_id_com_letra(self):
        self.assertIn("D-35b", self.d)
        self.assertNotIn("D-35", self.d)  # a D-35 está respondida e não se confunde com a D-35b
        self.assertNotIn("D-35c", self.d)  # tem **Resposta

    def test_resposta_da_35_nao_esconde_a_35b(self):
        m = a.mesclar_perguntas([], self.MD)
        self.assertEqual([q["id"] for q in m], ["D-35b", "D-44", "D-45", "D-46"])

    def test_letras_no_meio_do_texto_nao_sao_alternativas(self):
        self.assertEqual(self.d["D-35b"]["opcoes"], [])

    def test_bloco_de_opcoes_de_verdade(self):
        o = self.d["D-44"]["opcoes"]
        self.assertEqual([x["letra"] for x in o], ["a", "b"])

    def test_lista_dedicada_de_opcoes(self):
        o = self.d["D-46"]["opcoes"]
        self.assertEqual([x["texto"] for x in o], ["primeira", "segunda (recomendado)"])
        self.assertEqual([x["recomendada"] for x in o], [False, True])

    def test_decidido_pela_sessao_nao_fecha(self):
        self.assertIn("D-45", self.d)

    def test_sem_opcoes_vem_confirmo_e_quero_mudar(self):
        q = next(x for x in a.mesclar_perguntas([], self.MD) if x["id"] == "D-35b")
        self.assertEqual([(o["rotulo"], o["recomendada"]) for o in q["opcoes"]],
                         [("Confirmo", True), ("Quero mudar algo", False)])

    def test_quero_mudar_exige_texto(self):
        q = next(x for x in a.mesclar_perguntas([], self.MD) if x["id"] == "D-35b")
        erro, _ = a.validar_resposta({"id": "D-35b", "opcao": q["opcoes"][1]["letra"]}, [q])
        self.assertIsNotNone(erro)
        erro, limpo = a.validar_resposta({"id": "D-35b", "opcao": q["opcoes"][1]["letra"], "texto": "outra coisa"}, [q])
        self.assertIsNone(erro)
        erro, limpo = a.validar_resposta({"id": "D-35b", "opcao": q["opcoes"][0]["letra"]}, [q])
        self.assertIsNone(erro)
        self.assertEqual(limpo["opcao_texto"], "Confirmo")

    def test_id_repetido_mostra_as_duas_e_avisa(self):
        md = "### D-50. Primeira\n- x\n\n### D-50. Segunda\n- y\n"
        with self.assertLogs("painel.analisadores", level="WARNING") as lg:
            m = a.mesclar_perguntas([], md)
        self.assertEqual([(q["id"], q["pergunta"]) for q in m], [("D-50", "Primeira"), ("D-50", "Segunda")])
        self.assertIn("D-50", lg.output[0])


if __name__ == "__main__":
    unittest.main()
