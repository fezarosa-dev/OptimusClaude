"""Guarda o retorno de uma revisão em registros/revisoes/<data>-<tipo>.md.

    python3 scripts/registros/salvar_revisao.py <tipo> <arquivo>

<tipo>: revisao-profunda, security-review, claude-security, semgrep, insecure-defaults... (minúsculas, números, hífen).
<arquivo>: o JSON do workflow revisao-profunda, ou o markdown/texto de qualquer outra ferramenta. O JSON da revisão
profunda vira achados confirmados (com o veredito dos céticos), não verificados e derrubados (com o porquê); o resto
entra como está. O sha256 do arquivo original vai no cabeçalho: prova que a cópia é aquela.
Recusa (saída 1) relatório com segredo ou dado pessoal (ver sensivel.py). Não mexe no INDICE.md: ele é regenerado na dev.
Só biblioteca padrão.
"""
import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sensivel  # noqa: E402

PADRAO = Path(__file__).resolve().parents[2] / "registros"
TIPO = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")


def _commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=PADRAO.parent, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "indisponível"


def _celula(texto) -> str:
    return str(texto if texto is not None else "").replace("\r", " ").strip()


def _achado(a) -> str:
    local = f"{a.get('arquivo', '?')}:{a.get('linha', '?')}"
    linhas = [f"#### {local} · gravidade {a.get('gravidade', '?')}", "", _celula(a.get("resumo"))]
    for chave, rotulo in (("dimensao", "Dimensão"), ("cenario", "Cenário"), ("evidencia", "Evidência"),
                          ("votos", "Votos dos céticos (de pé/total)"), ("motivo", "Por que foi derrubado")):
        if a.get(chave):
            linhas.append(f"- **{rotulo}:** {_celula(a[chave])}")
    return "\n".join(linhas) + "\n"


def _secao(titulo, itens) -> str:
    corpo = "\n".join(_achado(a) for a in itens) if itens else "Nenhum.\n"
    return f"## {titulo} ({len(itens)})\n\n{corpo}\n"


def _corpo(dados: bytes) -> str:
    texto = dados.decode("utf-8", "replace")
    try:
        objeto = json.loads(texto)
    except ValueError:
        return texto.rstrip() + "\n"
    if isinstance(objeto, dict) and "confirmados" in objeto:
        cab = [f"- **Base:** `{_celula(objeto.get('base'))}`", f"- **Resumo:** {_celula(objeto.get('resumo'))}"]
        if objeto.get("aviso"):
            cab.append(f"- **Aviso:** {_celula(objeto['aviso'])}")
        return ("\n".join(cab) + "\n\n" + _secao("Confirmados", objeto.get("confirmados") or [])
                + _secao("Não verificados (os céticos falharam)", objeto.get("nao_verificados") or [])
                + _secao("Derrubados pelos céticos", objeto.get("derrubados") or []))
    return "```json\n" + json.dumps(objeto, ensure_ascii=False, indent=2) + "\n```\n"


def salvar(tipo, arquivo, pasta=PADRAO, hoje=None, commit=None) -> Path:
    if not TIPO.fullmatch(tipo or ""):
        raise ValueError(f"tipo inválido '{tipo}': minúsculas, números e hífen, até 40 caracteres")
    dados = Path(arquivo).read_bytes()
    if not dados.strip():
        raise ValueError(f"{arquivo} está vazio")
    hoje = hoje or datetime.date.today()
    cabecalho = (f"# Revisão: {tipo}, {hoje.isoformat()}\n\n"
                 f"- **Commit da árvore revisada (HEAD ao salvar):** `{commit or _commit()}`\n"
                 f"- **sha256 do relatório original:** `{hashlib.sha256(dados).hexdigest()}`\n\n")
    texto = cabecalho + _corpo(dados)
    # três visões: o arquivo cru, o cru sem o escape do JSON e o texto que vai ser gravado
    bruto = dados.decode("utf-8", "replace")
    achados = [f"linha {n} ({t})" for n, t in sensivel.achar(bruto)]
    achados += [f"linha {n} ({t}, sem o escape do JSON)" for n, t in sensivel.achar(sensivel.desescapar(bruto))]
    achados += [f"linha {n} ({t}, no texto gravado)" for n, t in sensivel.achar(texto)]
    if achados:  # o valor nunca volta na mensagem: só a linha e o tipo
        raise ValueError(f"{arquivo} tem segredo ou dado pessoal ({', '.join(dict.fromkeys(achados[:10]))}); "
                         "tire o valor do relatório e salve de novo")
    destino_dir = Path(pasta) / "revisoes"
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino, n = destino_dir / f"{hoje.isoformat()}-{tipo}.md", 1
    while destino.exists():
        n += 1
        destino = destino_dir / f"{hoje.isoformat()}-{tipo}-{n}.md"
    destino.write_text(texto, encoding="utf-8")
    return destino


def principal(args):
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        print(salvar(args[0], args[1]))
    except (ValueError, OSError) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
