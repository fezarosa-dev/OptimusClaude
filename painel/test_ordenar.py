"""Ordenação das listas do painel (ordenar.js), testada com node."""
import json, os, shutil, subprocess, unittest
from pathlib import Path

AQUI = Path(__file__).parent


def ordena(lista, tipo, ordem, ctx=None):
    js = "const {ordenar}=require(%s);const [l,t,o,c]=%s;console.log(JSON.stringify(ordenar(l,t,o,c)))" % (
        json.dumps(str(AQUI / "ordenar.js")), json.dumps([lista, tipo, ordem, ctx or {}]))
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)


@unittest.skipUnless(shutil.which("node"), "sem node")
class Ordenar(unittest.TestCase):
    def ids(self, *a, **k):
        return [x["id"] for x in ordena(*a, **k)]

    def tarefas(self):
        t = lambda i, est, seg=None, em=None, p=0: {"id": i, "estado": est, "percentual": p,
                                                    "tempo": None if seg is None else {"segundos": seg, "conclusao_em": em}}
        return [t(1, "concluida", 600), t(2, "andando", 300, 1000, 50), t(3, "fila", None), t(4, "fila", 900, 500, 0), t(5, "andando", 100, 2000, 90)]

    def test_padrao_andando_primeiro_e_numero_desc(self):
        self.assertEqual(self.ids(self.tarefas(), "tarefas", ""), [5, 2, 4, 3, 1])

    def test_falta_menor_e_maior_sem_tempo_e_concluida_no_fim(self):
        self.assertEqual(self.ids(self.tarefas(), "tarefas", "falta-menor"), [5, 2, 4, 1, 3])
        self.assertEqual(self.ids(self.tarefas(), "tarefas", "falta-maior"), [4, 2, 5, 1, 3])

    def test_previsao(self):
        self.assertEqual(self.ids(self.tarefas(), "tarefas", "previsao-cedo"), [4, 2, 5, 1, 3])
        self.assertEqual(self.ids(self.tarefas(), "tarefas", "previsao-tarde"), [5, 2, 4, 1, 3])

    def test_levou_so_concluidas(self):
        self.assertEqual(self.ids(self.tarefas(), "tarefas", "levou-menor")[0], 1)
        self.assertEqual(self.ids(self.tarefas(), "tarefas", "levou-maior")[0], 1)

    def test_pct_e_numero(self):
        self.assertEqual(self.ids(self.tarefas(), "tarefas", "pct-maior")[:2], [5, 2])
        self.assertEqual(self.ids(self.tarefas(), "tarefas", "numero-menor"), [1, 2, 3, 4, 5])

    def test_agentes_tempo_e_tokens(self):
        ag = [{"id": "a", "ativo": True, "inicio": 900}, {"id": "b", "ativo": True, "inicio": 500},
              {"id": "c", "ativo": False, "inicio": 100}, {"id": "d", "ativo": True, "inicio": 800}]
        ctx = {"agora": 1000, "consumo": {"agentes": {"a": 5, "b": 50, "c": 500}}}
        self.assertEqual(self.ids(ag, "agentes", "tempo-maior", ctx), ["b", "d", "a", "c"])
        self.assertEqual(self.ids(ag, "agentes", "tempo-menor", ctx), ["a", "d", "b", "c"])
        self.assertEqual(self.ids(ag, "agentes", "tokens-maior", ctx), ["c", "b", "a", "d"])
        self.assertEqual(self.ids(ag, "agentes", "tokens-menor", ctx), ["a", "b", "c", "d"])

    def test_workflows_duracao_e_tokens(self):
        wf = [{"id": "x"}, {"id": "y"}, {"id": "z"}]
        ctx = {"consumo": {"workflows": [{"id": "x", "segundos": 10, "tokens": 9}, {"id": "y", "segundos": 20, "tokens": 1}]}}
        self.assertEqual(self.ids(wf, "workflows", "duracao-maior", ctx), ["y", "x", "z"])
        self.assertEqual(self.ids(wf, "workflows", "tokens-maior", ctx), ["x", "y", "z"])

    def test_baterias_e_merges(self):
        b = [{"id": 1, "atividade": 5, "duracao": None}, {"id": 2, "atividade": 9, "duracao": 7}, {"id": 3, "atividade": 1, "duracao": 3}]
        self.assertEqual(self.ids(b, "baterias", "recente"), [2, 1, 3])
        self.assertEqual(self.ids(b, "baterias", "antiga"), [3, 1, 2])
        self.assertEqual(self.ids(b, "baterias", "duracao-maior"), [2, 3, 1])
        self.assertEqual(self.ids(b, "baterias", "duracao-menor"), [3, 2, 1])
        m = [{"id": 1, "quando": 1}, {"id": 2, "quando": 3}]
        self.assertEqual(self.ids(m, "merges", "recente"), [2, 1])

    def test_perguntas_antiga_e_nova(self):
        p = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        self.assertEqual(self.ids(p, "perguntas", "nova"), ["c", "b", "a"])
        self.assertEqual(self.ids(p, "perguntas", "antiga"), ["a", "b", "c"])

    def test_ordem_invalida_mantem_a_lista(self):
        p = [{"id": "a"}, {"id": "b"}]
        self.assertEqual(self.ids(p, "perguntas", "lixo"), ["a", "b"])


@unittest.skipUnless(shutil.which("node"), "sem node")
class MesclarOrdem(unittest.TestCase):
    def mescla(self, salva, atuais):
        js = "const {mesclarOrdem}=require(%s);console.log(JSON.stringify(mesclarOrdem(...%s)))" % (
            json.dumps(str(AQUI / "ordenar.js")), json.dumps([salva, atuais]))
        return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)

    def test_sem_ordem_salva_vale_a_de_hoje(self):
        self.assertEqual(self.mescla(None, ["a", "b", "c"]), ["a", "b", "c"])
        self.assertEqual(self.mescla("lixo", ["a", "b"]), ["a", "b"])

    def test_ordem_salva_vence(self):
        self.assertEqual(self.mescla(["c", "a", "b"], ["a", "b", "c"]), ["c", "a", "b"])

    def test_quadro_novo_entra_no_fim_e_o_que_sumiu_e_ignorado(self):
        self.assertEqual(self.mescla(["c", "x", "a"], ["a", "b", "c", "d"]), ["c", "a", "b", "d"])

    def test_repetido_na_ordem_salva_nao_duplica(self):
        self.assertEqual(self.mescla(["b", "b", "a"], ["a", "b"]), ["b", "a"])


@unittest.skipUnless(shutil.which("node"), "sem node")
class Grade(unittest.TestCase):
    """Grade de 3 colunas: quadros com posição {x,y} e tamanho P (1x1), M (2x1) ou G (3x2)."""
    def js(self, expr):
        js = "const o=require(%s);console.log(JSON.stringify(%s))" % (json.dumps(str(AQUI / "ordenar.js")), expr)
        return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)

    def sem_sobreposicao(self, lay):
        n = self.js("(()=>{const l=%s;let c=0;for(const k in l){const t=o.TAMANHOS[l[k].t];c+=t.w*t.h}return[c,Object.keys(o.ocupacao(l)).length]})()" % json.dumps(lay))
        self.assertEqual(n[0], n[1], lay)

    def test_tamanhos(self):
        self.assertEqual(self.js("o.TAMANHOS"), {"P": {"w": 1, "h": 1}, "M": {"w": 2, "h": 1}, "G": {"w": 3, "h": 2}})

    def test_ocupacao(self):
        self.assertEqual(self.js('o.ocupacao({a:{x:0,y:0,t:"M"},b:{x:2,y:0,t:"P"},c:{x:0,y:1,t:"P"}})'),
                         {"0,0": "a", "1,0": "a", "2,0": "b", "0,1": "c"})

    def test_cabe(self):
        L = '{a:{x:0,y:0,t:"M"},b:{x:2,y:0,t:"P"}}'
        for expr, esp in [('"c",0,1,"G"', True), ('"c",0,0,"P"', False), ('"c",2,1,"M"', False), ('"c",1,1,"G"', False),
                          ('"c",1,0,"P"', False), ('"a",0,0,"M"', True), ('"a",1,0,"M"', False), ('"c",-1,0,"P"', False),
                          ('"c",0,0,"G"', False), ('"c",0,2,"G"', True)]:
            self.assertEqual(self.js("o.cabe(%s,%s)" % (L, expr)), esp, expr)

    def test_auto_posicionar_primeiro_lugar_livre_linha_a_linha(self):
        r = self.js('o.autoPosicionar({},["a","b","c","d"],{a:"G",b:"P",c:"M",d:"P"})')
        self.assertEqual(r, {"a": {"x": 0, "y": 0, "t": "G"}, "b": {"x": 0, "y": 2, "t": "P"},
                             "c": {"x": 1, "y": 2, "t": "M"}, "d": {"x": 0, "y": 3, "t": "P"}})

    def test_auto_posicionar_mantem_quem_tem_posicao_e_ignora_quem_sumiu(self):
        r = self.js('o.autoPosicionar({a:{x:2,y:0,t:"P"},zz:{x:0,y:0,t:"P"}},["a","b"],"M")')
        self.assertEqual(r, {"a": {"x": 2, "y": 0, "t": "P"}, "b": {"x": 0, "y": 0, "t": "M"}})

    def test_auto_posicionar_posicao_que_nao_cabe_vai_para_lugar_livre(self):
        r = self.js('o.autoPosicionar({a:{x:0,y:0,t:"P"},b:{x:0,y:0,t:"P"}},["a","b"],"P")')
        self.sem_sobreposicao(r)
        self.assertEqual(r["a"], {"x": 0, "y": 0, "t": "P"})
        self.assertEqual(r["b"], {"x": 1, "y": 0, "t": "P"})

    def test_mover_para_lugar_vazio_e_prende_nas_colunas(self):
        L = '{a:{x:0,y:0,t:"M"}}'
        self.assertEqual(self.js("o.mover(%s,\"a\",5,2)" % L), {"a": {"x": 1, "y": 2, "t": "M"}})
        self.assertEqual(self.js("o.mover(%s,\"a\",-3,-1)" % L), {"a": {"x": 0, "y": 0, "t": "M"}})

    def test_mover_sobre_outro_troca_se_cabe_no_lugar_antigo(self):
        r = self.js('o.mover({a:{x:0,y:0,t:"P"},b:{x:1,y:0,t:"P"}},"a",1,0)')
        self.assertEqual(r, {"a": {"x": 1, "y": 0, "t": "P"}, "b": {"x": 0, "y": 0, "t": "P"}})

    def test_mover_sobre_outro_desce_se_nao_cabe_no_lugar_antigo(self):
        r = self.js('o.mover({a:{x:0,y:0,t:"M"},b:{x:2,y:0,t:"P"}},"b",1,0)')
        self.assertEqual(r, {"b": {"x": 1, "y": 0, "t": "P"}, "a": {"x": 0, "y": 1, "t": "M"}})

    def test_mover_nao_deixa_sobreposicao(self):
        L = {"a": {"x": 0, "y": 0, "t": "G"}, "b": {"x": 0, "y": 2, "t": "M"}, "c": {"x": 2, "y": 2, "t": "P"}, "d": {"x": 0, "y": 3, "t": "P"}}
        for k in L:
            for x in range(3):
                for y in range(5):
                    self.sem_sobreposicao(self.js("o.mover(%s,%s,%d,%d)" % (json.dumps(L), json.dumps(k), x, y)))

    def test_mover_chave_inexistente_nao_muda(self):
        L = {"a": {"x": 0, "y": 0, "t": "P"}}
        self.assertEqual(self.js("o.mover(%s,\"z\",1,1)" % json.dumps(L)), L)

    def test_redimensionar_empurra_quem_ficou_sobreposto(self):
        r = self.js('o.redimensionar({a:{x:0,y:0,t:"P"},b:{x:1,y:0,t:"P"},c:{x:2,y:0,t:"P"}},"a","M")')
        self.assertEqual(r, {"a": {"x": 0, "y": 0, "t": "M"}, "b": {"x": 0, "y": 1, "t": "P"}, "c": {"x": 2, "y": 0, "t": "P"}})

    def test_redimensionar_para_g_forca_coluna_zero(self):
        r = self.js('o.redimensionar({a:{x:0,y:0,t:"P"},b:{x:1,y:0,t:"P"},c:{x:2,y:0,t:"P"}},"b","G")')
        self.assertEqual(r, {"b": {"x": 0, "y": 0, "t": "G"}, "a": {"x": 0, "y": 2, "t": "P"}, "c": {"x": 1, "y": 2, "t": "P"}})

    def test_redimensionar_m_na_ultima_coluna_recua_uma(self):
        r = self.js('o.redimensionar({a:{x:2,y:0,t:"P"}},"a","M")')
        self.assertEqual(r, {"a": {"x": 1, "y": 0, "t": "M"}})

    def test_redimensionar_nunca_sobrepoe(self):
        L = {"a": {"x": 0, "y": 0, "t": "M"}, "b": {"x": 2, "y": 0, "t": "P"}, "c": {"x": 0, "y": 1, "t": "P"}, "d": {"x": 1, "y": 1, "t": "M"}}
        for k in L:
            for t in "PMG":
                self.sem_sobreposicao(self.js("o.redimensionar(%s,%s,%s)" % (json.dumps(L), json.dumps(k), json.dumps(t))))

    def test_ordem_linear_por_linha_e_depois_coluna(self):
        self.assertEqual(self.js('o.ordemLinear({a:{x:2,y:1,t:"P"},b:{x:0,y:1,t:"P"},c:{x:1,y:0,t:"P"},d:{x:0,y:0,t:"P"}})'), ["d", "c", "b", "a"])

    def test_migrar_do_formato_antigo(self):
        r = self.js('o.migrar({ordem:["b","a","c"],larguras:{a:6,b:2,c:3,d:4}},["a","b","c"],"M")')
        self.assertEqual(r, {"b": {"x": 0, "y": 0, "t": "P"}, "c": {"x": 1, "y": 0, "t": "M"}, "a": {"x": 0, "y": 1, "t": "G"}})

    def test_migrar_larguras_3_e_4_viram_medio_e_sem_largura_usa_o_padrao(self):
        r = self.js('o.migrar({ordem:["a","b"],larguras:{a:4}},["a","b"],{a:"G",b:"P"})')
        self.assertEqual(r, {"a": {"x": 0, "y": 0, "t": "M"}, "b": {"x": 2, "y": 0, "t": "P"}})

    def test_migrar_lixo_e_formato_so_ordem(self):
        for lixo in ["null", '"x"', "7", "{larguras:3}"]:
            r = self.js('o.migrar(%s,["a","b"],"P")' % lixo)
            self.assertEqual(r, {"a": {"x": 0, "y": 0, "t": "P"}, "b": {"x": 1, "y": 0, "t": "P"}}, lixo)
        r = self.js('o.migrar(["b","a"],["a","b"],"P")')
        self.assertEqual(r, {"b": {"x": 0, "y": 0, "t": "P"}, "a": {"x": 1, "y": 0, "t": "P"}})

    def test_valida_descarta_lixo_do_armazenamento(self):
        r = self.js("""o.valida_grade(JSON.parse('{"a":{"x":0,"y":0,"t":"P"},"b":{"x":3,"y":0,"t":"P"},"c":{"x":0,"y":1,"t":"X"},"d":{"x":1.5,"y":0,"t":"P"},"e":{"x":1,"y":0,"t":"G"},"f":{"x":0,"y":-1,"t":"P"},"g":"x","h":null,"i":{"x":"1","y":0,"t":"P"},"j":{"x":0,"y":0,"t":"M"},"zz":{"x":2,"y":0,"t":"P"},"__proto__":{"x":0,"y":9,"t":"P"}}'),["a","b","c","d","e","f","g","h","i","j"])""".replace("valida_grade", "validaGrade"))
        self.assertEqual(r, {"a": {"x": 0, "y": 0, "t": "P"}})

    def test_valida_lixo_que_nao_e_objeto(self):
        for lixo in ["null", '"x"', "7", "[1]"]:
            self.assertEqual(self.js("o.validaGrade(%s,[\"a\"])" % lixo), {}, lixo)

    def test_eh_padrao(self):
        P = '{a:{x:0,y:0,t:"P"},b:{x:1,y:0,t:"M"}}'
        self.assertTrue(self.js('o.ehPadrao({b:{x:1,y:0,t:"M"},a:{x:0,y:0,t:"P"}},%s)' % P))
        self.assertFalse(self.js('o.ehPadrao({a:{x:0,y:0,t:"P"},b:{x:1,y:0,t:"P"}},%s)' % P))
        self.assertFalse(self.js('o.ehPadrao({a:{x:0,y:0,t:"P"}},%s)' % P))

    def test_passo_de_tamanho_para_nas_pontas(self):
        for t, d, esp in [("P", 1, "M"), ("M", 1, "G"), ("G", 1, "G"), ("G", -1, "M"), ("M", -1, "P"), ("P", -1, "P")]:
            self.assertEqual(self.js("o.passoTamanho(%s,%s)" % (json.dumps(t), d)), esp, (t, d))


@unittest.skipUnless(shutil.which("node"), "sem node")
class Limites(unittest.TestCase):
    def js(self, expr):
        js = "const o=require(%s);console.log(JSON.stringify(%s))" % (json.dumps(str(AQUI / "ordenar.js")), expr)
        env = {**os.environ, "TZ": "UTC"}
        return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True, env=env).stdout)

    def test_faixa(self):
        for p, esp in [(None, "sem"), (0, "ok"), (69, "ok"), (70, "alerta"), (89, "alerta"), (90, "erro"), (100, "erro")]:
            self.assertEqual(self.js("o.faixaLimite(%s).faixa" % json.dumps(p)), esp, p)
        self.assertEqual(self.js("o.faixaLimite(95).texto"), "crítico")
        self.assertEqual(self.js("o.faixaLimite(75).texto"), "atenção")
        self.assertEqual(self.js("o.faixaLimite(10).texto"), "normal")

    def test_restante(self):
        for s, esp in [(None, ""), (0, "agora"), (-5, "agora"), (45, "45 s"), (17 * 60 + 20, "17 min"),
                       (2 * 3600 + 5 * 60, "2 h 5 min"), (3 * 3600, "3 h"), (6 * 86400 + 6 * 3600 + 100, "6 d 6 h"), (2 * 86400, "2 d")]:
            self.assertEqual(self.js("o.restante(%s)" % json.dumps(s)), esp, s)

    def test_volta_mesmo_dia_e_outro_dia(self):
        # 2026-11-01 (domingo) 12:00 UTC
        agora = 1793534400
        self.assertEqual(self.js("o.horaAlvo(%d,%d)" % (agora + 5 * 3600 + 2400, agora)), "17:40")
        self.assertEqual(self.js("o.horaAlvo(%d,%d)" % (agora + 6 * 86400 + 6 * 3600, agora)), "sáb 18:00")
        self.assertEqual(self.js("o.horaAlvo(null,%d)" % agora), "")

    def test_previsao(self):
        agora = 1793534400
        self.assertEqual(self.js("o.textoPrevisao({previsao_100_em:%d,ritmo_pct_por_hora:9},%d)" % (agora + 3600, agora)), "chega a 100% às 13:00")
        self.assertEqual(self.js("o.textoPrevisao({previsao_100_em:null,ritmo_pct_por_hora:4.5},%d)" % agora), "ritmo: 4,5%/h")
        self.assertEqual(self.js("o.textoPrevisao({previsao_100_em:null,ritmo_pct_por_hora:null},%d)" % agora), "")
        self.assertEqual(self.js("o.textoPrevisao(null,%d)" % agora), "")

    def test_grafico(self):
        # janela de 5 h terminando em 5000+18000; ponto no meio = 50% em x=50 de 100
        r = self.js("o.grafico([[14000,50],[14000,50]],23000,18000,100,40)")
        self.assertEqual(r["atual"], [50, 20])
        self.assertEqual(r["y100"], 0)
        self.assertEqual(self.js("o.grafico([],23000,18000,100,40)")["pontos"], "")
        # fora da janela é ignorado; pct acima de 100 é limitado
        r = self.js("o.grafico([[1,10],[23000,150]],23000,18000,100,40)")
        self.assertEqual(r["atual"], [100, 0])


if __name__ == "__main__":
    unittest.main()
