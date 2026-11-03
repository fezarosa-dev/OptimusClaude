"""Effort dos agentes: do meta (avulsos) ou do começo do histórico (agentes de workflow)."""
import json
import os
import shutil
import tempfile
import unittest

import fontes
import shells as sh


def reg(effort, enchimento=0):
    """Um registro de pedido como o do histórico do agente; `enchimento` empurra o marcador para longe do começo."""
    return json.dumps({"type": "api-request", "pad": "x" * enchimento, "output_config": {"effort": effort}}) + "\n"


class LerEffort(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p = os.path.join(self.tmp, "agent-x.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def escrever(self, texto):
        with open(self.p, "w") as f:
            f.write(texto)

    def test_pega_a_primeira_ocorrencia(self):
        self.escrever('{"type":"user"}\n' + reg("high") + reg("max"))
        self.assertEqual(fontes.effort_do_historico(self.p), "high")

    def test_sem_nada_ou_sem_arquivo_e_vazio(self):
        self.escrever('{"type":"user"}\n')
        self.assertEqual(fontes.effort_do_historico(self.p), "")
        self.assertEqual(fontes.effort_do_historico(self.p + ".nao-existe"), "")

    def test_arquivo_grande_e_lido_so_no_comeco(self):
        self.escrever(reg("xhigh") + "y" * (6 << 20))
        self.assertEqual(fontes.effort_do_historico(self.p), "xhigh")
        # marcador depois do limite lido: não acha (prova que não carrega o arquivo inteiro)
        self.escrever("y" * (fontes.EFFORT_LIMITE + (64 << 10)) + "\n" + reg("max"))
        self.assertEqual(fontes.effort_do_historico(self.p, {}), "")

    def test_limite_esgotado_nao_relê_quando_cresce(self):
        cache = {}
        self.escrever("y" * (fontes.EFFORT_LIMITE + (64 << 10)))
        self.assertEqual(fontes.effort_do_historico(self.p, cache), "")
        with open(self.p, "a") as f:
            f.write(reg("max"))  # cresceu, mas o começo já foi todo lido sem achar: não lê de novo
        ab = os.path.getsize(self.p)
        os.utime(self.p)
        self.assertEqual(fontes.effort_do_historico(self.p, cache), "")
        self.assertEqual(cache[self.p][0], ab - len(reg("max")))  # nada foi relido: o tamanho em cache é o antigo

    def test_marcador_cortado_entre_dois_pedacos(self):
        pad = "z" * (fontes.EFFORT_PEDACO - 20)
        self.escrever(pad + '"output_config":{"effort":"medium"}\n')
        self.assertEqual(fontes.effort_do_historico(self.p), "medium")

    def test_cache_nao_relê_e_vazio_tenta_de_novo_quando_cresce(self):
        cache = {}
        self.escrever('{"type":"user"}\n')
        self.assertEqual(fontes.effort_do_historico(self.p, cache), "")
        with open(self.p, "a") as f:
            f.write(reg("high"))
        self.assertEqual(fontes.effort_do_historico(self.p, cache), "high")
        os.remove(self.p)  # com o valor em cache, nem precisa do arquivo
        self.assertEqual(fontes.effort_do_historico(self.p, cache), "high")


class NoEstado(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sd = os.path.join(self.tmp, "sess")
        for d in ("/subagents/workflows/wf_a", "/workflows"):
            os.makedirs(self.sd + d)
        fontes._EFFORT.clear()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def agente(self, caminho, meta, jsonl):
        with open(f"{self.sd}/subagents/{caminho}.meta.json", "w") as f:
            json.dump(meta, f)
        with open(f"{self.sd}/subagents/{caminho}.jsonl", "w") as f:
            f.write(jsonl)

    def test_avulso_usa_o_meta_e_workflow_le_do_historico(self):
        self.agente("agent-av", {"description": "avulso", "model": "sonnet", "effort": "high"}, '{"type":"user"}\n')
        self.agente("workflows/wf_a/agent-w1", {"description": "wf", "model": "opus"}, reg("xhigh"))
        self.agente("workflows/wf_a/agent-w2", {"description": "sem", "model": "opus"}, '{"type":"user"}\n')
        ags, _ = fontes.agentes_e_workflows({"ativo_segundos": 120}, self.sd)
        ef = {x["id"]: x["effort"] for x in ags}
        self.assertEqual(ef, {"av": "high", "w1": "xhigh", "w2": ""})

    def test_workflow_traz_os_efforts_dos_agentes(self):
        self.agente("workflows/wf_a/agent-w1", {"model": "opus"}, reg("max"))
        self.agente("workflows/wf_a/agent-w2", {"model": "opus"}, reg("high"))
        with open(self.sd + ".jsonl", "w") as f:
            f.write("")
        for n in ("w1", "w2"):
            with open(f"{self.sd}/subagents/workflows/wf_a/agent-{n}.jsonl", "a") as f:
                f.write(json.dumps({"type": "assistant", "timestamp": "2026-11-01T10:00:00Z", "message": {
                    "id": n, "model": "claude-opus-5-5", "usage": {"output_tokens": 5}}}) + "\n")
        c = fontes.consumo(self.sd, {})
        self.assertEqual(c["workflows"][0]["efforts"], ["high", "max"])  # na ordem medium < high < xhigh < max


class Reforcos(unittest.TestCase):
    def test_cabecalho_desconhecido_e_mascarado(self):
        for t, segredo in [('curl -H "X-Api-Key: abc123def" u', "abc123def"), ("curl -H 'X-Auth: zzz999' u", "zzz999"),
                           ("curl --header 'Cookie-Foo: valorsecreto' u", "valorsecreto"),
                           ("curl -H 'Proxy-Authorization: Basic Zm9v' u", "Zm9v"), ("curl -H X-Custom:meuvalor u", "meuvalor"),
                           ('curl -H"X-Auth: zzz999" u', "zzz999"), ("curl -HX-Auth:zzz999 u", "zzz999"),
                           ("curl -H $'X-Auth: zzz999' u", "zzz999"), ("curl -H$'X-Auth: zzz999' u", "zzz999")]:
            m = sh.mascarar(t)
            self.assertNotIn(segredo, m, m)

    def test_cabecalho_inofensivo_fica(self):
        t = 'curl -s -H "Content-Type: application/json" -H "Title: Claude precisa de voce" -H "Tags: question" -H "Accept: */*" u'
        self.assertEqual(sh.mascarar(t), t)

    def test_corpo_de_chave_privada(self):
        corpo = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7\nabcDEFghiJKLmnoPQRstuVWXyz0123456789+/AAAA"
        t = f"echo -----BEGIN PRIVATE KEY-----\n{corpo}\n-----END PRIVATE KEY----- depois"
        m = sh.mascarar(t)
        self.assertNotIn("MIIEvQ", m)
        self.assertNotIn("abcDEF", m)
        self.assertIn("depois", m)
        self.assertNotIn("abcDEF", "\n".join(sh._linhas(t)))  # a saída é mascarada linha a linha: a chave tem de cair antes
        m2 = sh.mascarar("-----BEGIN RSA PRIVATE KEY-----\nqwertyuiop\n")  # fim cortado: some tudo até o fim do texto
        self.assertNotIn("qwertyuiop", m2)

    def test_fim_so_conta_na_ultima_linha_nao_vazia(self):
        r = sh.estado_terminado("o script imprimiu\n[exited with code 3]\nmas ainda segue rodando\n", None)
        self.assertIsNone(r)
        r = sh.estado_terminado("ok\n[exited with code 3]\n\n  \n", None)
        self.assertEqual((r["estado"], r["codigo"]), ("falhou", 3))


if __name__ == "__main__":
    unittest.main()
