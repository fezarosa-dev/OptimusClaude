"""Acha segredo e dado pessoal num texto, para nada disso entrar em registros/.

    achar(texto) -> [(número da linha, tipo)]   # nunca devolve o valor

Usado por salvar_revisao.py e pelos testes. Só biblioteca padrão. Para o seu projeto, acrescente em PADROES os
prefixos de chave dos serviços que você usa, e em DOMINIOS_DE_TESTE os domínios do seu dado fictício.
"""
import re

PADROES = [
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{10,}")),
    ("Authorization/Bearer", re.compile(r"(?i)\b(authorization\s*:|bearer\s+)[A-Za-z0-9._~+/=-]{12,}")),
    ("Cookie", re.compile(r"(?i)^\s*(set-)?cookie\s*:\s*\S+=")),
    ("chave privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("chave AWS", re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("token GitHub", re.compile(r"\b(ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}")),
    ("token Slack", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("chave de API", re.compile(r"\b(sk|rk)-[A-Za-z0-9_-]{24,}")),
    ("senha em URL", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s/@]+@")),
]
DOMINIOS_DE_TESTE = ("example.com", "example.org", "example.net", "exemplo.com", "test", "invalid", "localhost")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b")
CPF = re.compile(r"(?<![\d.])(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})(?![\d.])")
CNPJ = re.compile(r"(?<![\d.])(\d{2})\.?(\d{3})\.?(\d{3})/?(\d{4})-?(\d{2})(?![\d.])")


def _cpf_valido(numeros):
    if len(set(numeros)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d) * peso for d, peso in zip(numeros[:tamanho], range(tamanho + 1, 1, -1)))
        if (soma * 10 % 11) % 10 != int(numeros[tamanho]):
            return False
    return True


def _cnpj_valido(numeros):
    if len(set(numeros)) == 1:
        return False
    for tamanho in (12, 13):
        pesos = list(range(tamanho - 7, 1, -1)) + list(range(9, 1, -1))
        resto = sum(int(d) * p for d, p in zip(numeros[:tamanho], pesos)) % 11
        if (0 if resto < 2 else 11 - resto) != int(numeros[tamanho]):
            return False
    return True


def _email_real(dominio):
    dominio = dominio.lower()
    return not any(dominio == d or dominio.endswith("." + d) for d in DOMINIOS_DE_TESTE)


def achar(texto):
    achados = []
    for n, linha in enumerate(texto.splitlines(), 1):
        tipos = [nome for nome, padrao in PADROES if padrao.search(linha)]
        if any(_cpf_valido("".join(m.groups())) for m in CPF.finditer(linha)):
            tipos.append("CPF")
        if any(_cnpj_valido("".join(m.groups())) for m in CNPJ.finditer(linha)):
            tipos.append("CNPJ")
        if any(_email_real(m.group(1)) for m in EMAIL.finditer(linha)):
            tipos.append("e-mail")
        achados += [(n, t) for t in dict.fromkeys(tipos)]
    return achados


def desescapar(texto):
    """O texto cru de um JSON sem o escape (\\n, \\/, \\uXXXX), para achar o que o escape esconderia."""
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)),
                  texto.replace("\\n", "\n").replace("\\/", "/").replace('\\"', '"'))
