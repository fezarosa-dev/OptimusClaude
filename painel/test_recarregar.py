"""POST /api/recarregar: mesmas proteções do /api/responder; zera caches e acorda os laços de fundo."""
import json
import unittest

import fontes
import servidor as s
from test_servidor import Base, IP_REDE

CAB = {"X-Painel": "1"}


class TestRecarregar(Base):
    def rec(self, cab=None, **kw):
        return self.req("POST", "/api/recarregar", None, cab, **kw)

    def test_sem_x_painel_recusado(self):
        self.assertEqual(self.rec().status, 403)

    def test_zera_caches_e_troca_dicts(self):
        s._cache["t"] = s._git["t"] = s._nomes["t"] = fontes._docker_cache["t"] = 123
        antigos = (s._consumo["cache"], s._shells["cache"], fontes._EFFORT)
        r = self.rec(CAB)
        self.assertEqual(r.status, 200)
        self.assertEqual(json.loads(r.corpo), {"ok": True})
        self.assertEqual((s._cache["t"], s._git["t"], s._nomes["t"], fontes._docker_cache["t"]), (0, 0, 0, 0))
        self.assertIsNot(s._consumo["cache"], antigos[0])
        self.assertIsNot(s._shells["cache"], antigos[1])
        self.assertIsNot(fontes._EFFORT, antigos[2])

    def test_acorda_os_quatro_lacos(self):
        for ev in s._acordar.values():
            ev.clear()
        self.rec(CAB)
        self.assertEqual(len(s._acordar), 4)
        self.assertTrue(all(ev.is_set() for ev in s._acordar.values()))

    def test_origem_diferente_recusada(self):
        self.assertEqual(self.rec({**CAB, "Origin": "http://outro.com"}).status, 403)

    def test_outra_rota_post_404(self):
        self.assertEqual(self.req("POST", "/api/outra", None, CAB).status, 404)


@unittest.skipUnless(IP_REDE, "sem IP de rede")
class TestRecarregarRemoto(Base):
    endereco = IP_REDE

    def test_remoto_sem_chave_recusado(self):
        self.assertEqual(self.req("POST", "/api/recarregar", None, CAB).status, 403)

    def test_remoto_com_cookie_ok(self):
        self.assertEqual(self.req("POST", "/api/recarregar", None, {**CAB, "Cookie": "painel_chave=" + s.CHAVE}).status, 200)


if __name__ == "__main__":
    unittest.main()
