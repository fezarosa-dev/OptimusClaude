"""Quadro 'Linhas desde a main': git diff <ramo_base>...<ramo> (padrão origin/main...dev) somado por categoria. Só lê (git diff/rev-list/worktree list)."""
import os
import re
import subprocess

import shells

CATEGORIAS = [
    ("sql", "SQL (migrations e testes SQL)"), ("py", "Python, código"), ("py_teste", "Python, testes"),
    ("ts", "TypeScript/TSX, código"), ("ts_teste", "TypeScript/TSX, testes"), ("shell", "Shell e PowerShell"),
    ("config", "Config"), ("lock", "Lockfiles"), ("md", "Markdown"), ("registros", "Registros (provas)"),
]
CODIGO = ("sql", "py", "py_teste", "ts", "ts_teste", "shell")
_TESTE_PY = re.compile(r"(^|/)(tests?|testes)/|(^|/)test_[^/]*$|_test\.py$|(^|/)conftest\.py$")
_RENOME = re.compile(r"\{[^{}]* => ([^{}]*)\}")


def _destino(caminho):
    """Renomeado aparece como 'a/{x => y}/b' ou 'x => y': a categoria é a do destino."""
    if " => " not in caminho:
        return caminho
    c = _RENOME.sub(lambda m: m.group(1), caminho)
    return c.split(" => ")[-1].replace("//", "/") if " => " in c else c.replace("//", "/")


def categoria(caminho):
    p = _destino(caminho)
    base = os.path.basename(p)
    ext = os.path.splitext(base)[1].lower()
    if p.startswith("registros/"):
        return "registros"
    if base.startswith("package-lock") or base.endswith(".lock") or base.startswith("constraints"):
        return "lock"
    if ext == ".sql":
        return "sql"
    if ext == ".py":
        return "py_teste" if _TESTE_PY.search(p) else "py"
    if ext in (".ts", ".tsx", ".js", ".mjs"):
        return "ts_teste" if re.search(r"\.(test|spec)\.|(^|/)e2e/", p) else "ts"
    if ext in (".sh", ".ps1", ".psm1"):
        return "shell"
    return "md" if ext == ".md" else "config"


def somar(numstat):
    """numstat -> {categoria: (adicionadas, removidas)}; o caminho vem depois do 2º TAB (aceita espaço no nome); binário ('-') fica fora."""
    r = {}
    for l in numstat.splitlines():
        partes = l.split("\t", 2)
        if len(partes) < 3 or not (partes[0].isdigit() and partes[1].isdigit()):
            continue
        c = categoria(partes[2])
        a, d = r.get(c, (0, 0))
        r[c] = (a + int(partes[0]), d + int(partes[1]))
    return r


def codigo_e_testes(por):
    return sum(por.get(c, (0, 0))[0] for c in CODIGO)


def shortstat(txt):
    ins = re.search(r"(\d+) insertion", txt)
    dele = re.search(r"(\d+) deletion", txt)
    return (int(ins.group(1)) if ins else 0, int(dele.group(1)) if dele else 0)


def _git(args, cwd, timeout=20):
    r = subprocess.run(["git", "--no-optional-locks", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError((r.stderr.strip().splitlines() or [f"git saiu com {r.returncode}"])[-1])
    return r.stdout


def _worktrees(cfg, aviso):
    saida, atual = [], {}
    for l in _git(["worktree", "list", "--porcelain"], cfg["projeto"]).splitlines() + [""]:
        if l:
            k, _, v = l.partition(" ")
            atual[k] = v
        else:
            if atual.get("worktree", "").startswith(cfg["worktrees"]) and atual.get("HEAD"):
                saida.append(atual)
            atual = {}
    res = []
    for w in saida:
        pasta, ramo = w["worktree"], w.get("branch", "").replace("refs/heads/", "") or os.path.basename(w["worktree"])
        try:
            if int(_git(["rev-list", "--count", f"{cfg.get('ramo') or 'dev'}..HEAD"], pasta).strip() or 0) <= 0:
                continue
            a, r = shortstat(_git(["diff", "--shortstat", f"{cfg.get('ramo') or 'dev'}...HEAD"], pasta))
            ca, cr = shortstat(_git(["diff", "--shortstat"], pasta))
        except Exception as e:
            aviso(f"worktree {os.path.basename(pasta)}: {e}")
            continue
        res.append({"ramo": shells.mascarar(ramo), "a_frente": {"adicionadas": a, "removidas": r},
                    "por_commitar": {"adicionadas": ca, "removidas": cr}})
    return res


def coletar(cfg):
    faixa = f"{cfg.get('ramo_base') or 'origin/main'}...{cfg.get('ramo') or 'dev'}"
    avisos = []
    aviso = lambda t: avisos.append(shells.mascarar(t))
    por, arq, wts = {}, {"adicionados": 0, "modificados": 0, "removidos": 0}, []
    try:
        por = somar(_git(["diff", "--numstat", faixa], cfg["projeto"]))
        for l in _git(["diff", "--name-status", faixa], cfg["projeto"]).splitlines():
            s = l.split("\t", 1)[0][:1]
            arq["adicionados" if s == "A" else "removidos" if s == "D" else "modificados"] += 1 if s else 0
    except Exception as e:
        aviso(f"git diff {faixa}: {e}")
    try:
        wts = _worktrees(cfg, aviso)
    except Exception as e:
        aviso(f"worktrees: {e}")
    return {
        "categorias": [{"chave": k, "nome": n, "adicionadas": por.get(k, (0, 0))[0], "removidas": por.get(k, (0, 0))[1]} for k, n in CATEGORIAS],
        "total": {"adicionadas": sum(a for a, _ in por.values()), "removidas": sum(d for _, d in por.values())},
        "codigo_e_testes": codigo_e_testes(por), "arquivos": arq, "worktrees": wts, "avisos": avisos, "faixa": faixa,
    }
