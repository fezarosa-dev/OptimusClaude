"""O CSS do index.html tem as chaves balanceadas: uma chave aberta a mais engole o resto da folha num @media."""
import re
import unittest
from pathlib import Path

HTML = (Path(__file__).resolve().parent / "index.html").read_text()


class Css(unittest.TestCase):
    def test_chaves_balanceadas_no_css(self):
        css = re.sub(r"/\*.*?\*/", "", HTML[HTML.index("<style>"):HTML.index("</style>")], flags=re.S)
        prof = 0
        for c in css:
            prof += {"{": 1, "}": -1}.get(c, 0)
            self.assertGreaterEqual(prof, 0, "chave fechada sem abrir")
        self.assertEqual(prof, 0, "chave aberta sem fechar: o CSS seguinte fica preso no @media")


if __name__ == "__main__":
    unittest.main()
