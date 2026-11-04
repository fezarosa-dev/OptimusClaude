"""Decide o que testar pelo que mudou. Um mapa só, usado na máquina (scripts/testar_como_o_ci.py) e no CI.

    python3 scripts/o_que_testar.py ARQUIVO...      # nomes das verificações, uma por linha
    python3 scripts/o_que_testar.py --tudo          # todas as verificações
    python3 scripts/o_que_testar.py --mostrar NOME  # "programas<TAB>comando" da verificação

Sem arquivo nenhum: só o que roda sempre. Na dúvida testa a mais: caminho que o mapa não conhece roda TUDO.
Só biblioteca padrão (roda antes de qualquer instalação).

Para adaptar ao seu projeto: acrescente verificações em VERIFICACOES (os programas de que precisa e o comando)
e diga no MAPA quais caminhos ligam cada uma. Os exemplos comentados mostram Python, Node e SQL.
"""
import sys

# nome: (programas que precisam existir, comando rodado pelo shell da plataforma na raiz do repositório: sh no
# Linux/macOS, cmd no Windows. Use aspas duplas, que os dois entendem; && funciona nos dois).
# Programa que falta vira PULADO (e reprova com EXIGIR_TUDO=1).
VERIFICACOES = {
    "segredos": (["gitleaks"], "gitleaks git --no-banner --redact . && gitleaks dir --no-banner --redact ."),
    "scripts": (["python3"], 'python3 -I -m unittest discover -s scripts -p "test_*.py"'),
    "shell": (["shellcheck", "xargs"], 'git ls-files -z "*.sh" | xargs -0 -r shellcheck'),
    "actions": (["actionlint"], "actionlint"),
    # "python": (["uv"], "uv run --frozen pytest -q && uvx ruff check ."),
    # "node": (["npm"], "cd web && npm ci && npm run lint && npm test && npm run build"),
    # "tela": (["npm"], "cd web && npx playwright test"),
    # "sql": (["docker"], "bash scripts/testes_sql.sh"),
}

# o que roda em toda bateria, mude o que mudar
SEMPRE = ["segredos", "scripts"]

# (prefixo do caminho, verificações). O primeiro que casa vence; prefixo terminado em "/" é pasta.
MAPA = [
    (".github/workflows/", ["actions"]),
    ("scripts/", ["scripts", "shell"]),
    (".githooks/", ["scripts"]),
    ("registros/", []),
    ("docs/", []),
    # ("src/", ["python"]),
    # ("tests/", ["python"]),
    # ("web/", ["node", "tela"]),
    # ("supabase/migrations/", ["sql"]),
]

# extensões que nunca ligam teste além do SEMPRE
SO_TEXTO = (".md", ".txt")


def _passos(caminho):
    for prefixo, passos in MAPA:
        if caminho == prefixo or caminho.startswith(prefixo):
            return set(passos)
    if caminho.endswith(SO_TEXTO):
        return set()
    if caminho.endswith(".sh"):
        return {"shell"}
    print(f"o mapa não conhece {caminho}: roda tudo", file=sys.stderr)
    return set(VERIFICACOES)


def decidir(arquivos):
    return sorted(set(SEMPRE).union(*(_passos(a) for a in arquivos)))


def mostrar(nome):
    programas, comando = VERIFICACOES[nome]
    return " ".join(programas) + "\t" + comando


def principal(args):
    if args[:1] == ["--mostrar"] and len(args) == 2:
        if args[1] not in VERIFICACOES:
            print(f"verificação desconhecida: {args[1]}", file=sys.stderr)
            return 2
        print(mostrar(args[1]))
        return 0
    print("\n".join(sorted(VERIFICACOES) if args == ["--tudo"] else decidir(args)))
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
