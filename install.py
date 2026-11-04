#!/usr/bin/env python3
"""Instala a configuração do Claude Code deste repositório (Linux, macOS, WSL e Windows; só biblioteca padrão).

  claude/*  -> ~/.claude          (com backup do que já existe e for diferente)
  painel/   -> ~/painel-da-sessao (idem; arquivos de estado do painel não são tocados)
Depois checa (e instala, quando há instalador seguro) as dependências e os plugins.
Idempotente: rodar de novo só copia o que mudou. Não copia settings.example.json como settings.json,
test_*.py, *.pyc nem __pycache__.

Uso: python3 install.py [--dry-run] [--so-checar] [--sem-plugins] [--mesclar-settings]
     (./install.sh e install.ps1 só conferem o Python e chamam este arquivo)
  --dry-run           mostra o que faria, sem mudar nada
  --so-checar         não grava nada (nem cópia, nem backup, nem settings, nem instalação): só confere e
                      lista o que falta e os arquivos que seriam copiados
  --sem-plugins       pula marketplaces e plugins do Claude Code
  --mesclar-settings  mescla settings.example.json no ~/.claude/settings.json existente (objetos mesclados,
                      arrays juntados sem duplicata e sem reordenar (os do usuário primeiro), escalar do
                      usuário vence; mostra o diff e pede confirmação)
"""
import argparse
import difflib
import filecmp
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

MARKETPLACES = ["anthropics/claude-plugins-official", "mksglu/context-mode", "DietrichGebert/ponytail",
                "trailofbits/skills", "guillaumemeyer/watermarks-remover", "latent-spaces/brag"]
PLUGINS = ["superpowers@claude-plugins-official", "claude-code-setup@claude-plugins-official",
           "skill-creator@claude-plugins-official", "code-simplifier@claude-plugins-official",
           "claude-security@claude-plugins-official", "security-guidance@claude-plugins-official",
           "pyright-lsp@claude-plugins-official", "typescript-lsp@claude-plugins-official",
           "context-mode@context-mode", "ponytail@ponytail", "insecure-defaults@trailofbits",
           "watermarks-remover@watermarks-remover", "brag@brag"]
MODS_MP = "optimus-mods"
MODS_PLUGINS = ["status-bar@" + MODS_MP, "painel-agentes@" + MODS_MP]
MCP_SERENA = ["mcp", "add", "-s", "user", "serena", "--", "serena", "start-mcp-server",
              "--context", "claude-code", "--project-from-cwd"]
SO_NOME = ("windows" if os.name == "nt" else "mac" if sys.platform == "darwin" else "linux")
STATUSLINE_PAINEL = 'python3 \\"$HOME/painel-da-sessao/statusline.py\\"'
STATUSLINE_AVULSA = 'python \\"$HOME/.claude/statusline/statusline.py\\"'
PKG = "instale pelo gerenciador de pacotes do sistema"


def _comandos(entradas):
    """Comandos de uma lista de entradas de hook ({matcher, hooks:[{command}]}); tolerante a formato estranho."""
    out = []
    for e in entradas:
        hs = e.get("hooks") if isinstance(e, dict) else None
        out += [h["command"] for h in hs if isinstance(h, dict) and "command" in h] if isinstance(hs, list) else []
    return out


def mesclar(a, b, caminho=()):
    """Mescla a (exemplo) com b (usuário): objetos em profundidade, chaves do usuário primeiro; arrays do usuário
    na ordem dele e depois os do exemplo que faltam; no resto o usuário vence. Mesma semântica do antigo JQ_MESCLA,
    mais uma regra: em hooks.<evento> não entra entrada do exemplo cujos commands o usuário já tem no evento."""
    if isinstance(a, dict) and isinstance(b, dict):
        r = {}
        for k in list(b) + list(a):
            if k in r:
                continue
            r[k] = mesclar(a[k], b[k], caminho + (k,)) if k in a and k in b else (b[k] if k in b else a[k])
        return r
    if isinstance(a, list) and isinstance(b, list):
        if len(caminho) == 2 and caminho[0] == "hooks":
            ja = set(_comandos(b))
            return b + [x for x in a if x not in b and not (_comandos([x]) and set(_comandos([x])) & ja)]
        return b + [x for x in a if x not in b]
    return b


def python_ok(versao=None):
    return tuple((versao or sys.version_info)[:2]) >= (3, 9)


def tem_hook_rtk(j):
    """True/False, ou None se o settings tem um formato que não dá para conferir."""
    if not isinstance(j, dict):
        return None
    hooks = j.get("hooks", {})
    if not isinstance(hooks, dict):
        return None
    pre = hooks.get("PreToolUse", [])
    if not isinstance(pre, list) or any(not isinstance(e, dict) or not isinstance(e.get("hooks", []), list) for e in pre):
        return None
    return any("rtk hook" in c for c in _comandos(pre))


def dependencias(so):
    """(binário, nível, como instalar à mão, comando de instalação ou None) conforme o SO."""
    win = so == "windows"
    return [
        ("git", "obrigatória", "winget install Git.Git (traz o Git Bash, que o Claude Code usa no Windows)" if win else PKG,
         None),
        ("node", "obrigatória", ("winget install OpenJS.NodeJS.LTS; " if win else "https://nodejs.org (ou fnm/nvm); ")
         + "precisa para context-mode e caveman", None),
        ("uv", "obrigatória", "winget install astral-sh.uv" if win else "curl -LsSf https://astral.sh/uv/install.sh | sh",
         None),
        ("rtk", "obrigatória", "veja https://github.com/rtk-ai/rtk (" + ("binário da release ou cargo" if win else "script de instalação ou cargo")
         + "); depois 'rtk init -g'", None),
        ("caveman", "obrigatória", "npm i -g @caveman-ai/cli; depois 'caveman hooks install claude'",
         ["npm", "i", "-g", "@caveman-ai/cli"]),
        ("serena", "obrigatória", "uv tool install serena-agent", "uvtool:serena-agent"),
        ("ccc", "obrigatória", "uv tool install cocoindex-code", "uvtool:cocoindex-code"),
        ("gh", "recomendada", "winget install GitHub.cli" if win else "https://cli.github.com", None),
        ("jq", "recomendada", "winget install jqlang.jq" if win else PKG, None),
        ("gitleaks", "recomendada", "winget install Gitleaks.Gitleaks" if win else
         "https://github.com/gitleaks/gitleaks (binário da release ou gerenciador de pacotes)", None),
        ("semgrep", "opcional", "uv tool install semgrep", "uvtool:semgrep"),
        ("curl", "recomendada", "já vem no Windows 10 e 11 (curl.exe); os avisos do ntfy usam" if win
         else PKG + "; os avisos do ntfy usam", None),
    ]


class Instalador:
    def __init__(self, args, home=None, raiz=None, path=None, env=None, entrada=input, saida=print, orcamento=True,
                 so=SO_NOME):
        self.a = args
        self.dry = args.dry_run or args.so_checar
        self.so_checar = args.so_checar
        self.home = Path(home or Path.home())
        self.raiz = Path(raiz or Path(__file__).resolve().parent)
        self.path = path  # None = PATH do processo
        self.env = os.environ if env is None else env
        self.entrada, self.say, self.orcamento, self.so = entrada, saida, orcamento, so
        self.claude_dir = Path(self.env.get("CLAUDE_CONFIG_DIR") or self.home / ".claude")
        self.painel_dir = self.home / "painel-da-sessao"
        base = self.claude_dir / "backups" / ("optimusclaude-" + time.strftime("%Y%m%d-%H%M%S"))
        self.backup, n = base, 1
        while self.backup.exists():  # duas rodadas no mesmo segundo não misturam backups
            n += 1
            self.backup = base.with_name(f"{base.name}-{n}")
        self.falta, self.feito = [], 0

    # -- utilidades ---------------------------------------------------------------------------------------
    def which(self, bin_):
        return shutil.which(bin_, path=self.path)

    def tem(self, bin_):
        return self.which(bin_) is not None

    def _exec(self, cmd):
        env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home))
        if self.path is not None:
            env["PATH"] = self.path
        cmd = [self.which(cmd[0]) or cmd[0]] + list(cmd[1:])
        try:
            return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600)
        except (OSError, subprocess.SubprocessError):
            return None

    def ler(self, cmd):
        """Saída de um comando só de leitura (roda mesmo em --dry-run, como nos scripts antigos)."""
        r = self._exec(cmd)
        return (r.stdout or "") if r else ""

    def ok(self, cmd):
        r = self._exec(cmd)
        return bool(r) and r.returncode == 0

    def rodar(self, cmd, descricao=None):
        """Roda um comando que grava; em --dry-run só descreve, em --so-checar nem isso."""
        if self.so_checar:
            return True
        if self.dry:
            self.say("  [dry-run] " + (descricao or " ".join(cmd)))
            return True
        return self.ok(cmd)

    def anotar(self, texto):
        self.falta.append(texto)

    # -- cópia --------------------------------------------------------------------------------------------
    def copiar(self, src, dst, rel):
        if dst.is_file() and filecmp.cmp(src, dst, shallow=False):
            return
        if not self.dry:
            if dst.exists():
                bk = self.backup / rel
                bk.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, bk)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        self.say(("  [dry-run] copiar " if self.a.dry_run and not self.so_checar else "  ") + rel)
        self.feito += 1

    def copiar_arvore(self, origem, destino, prefixo):
        for f in sorted(origem.rglob("*")):
            n = f.name
            if (not f.is_file() or n == "settings.example.json" or n.endswith(".pyc") or "__pycache__" in f.parts
                    or (n.startswith("test_") and n.endswith(".py"))):
                continue
            rel = f.relative_to(origem).as_posix()
            self.copiar(f, destino / rel, prefixo + rel)

    # -- etapas -------------------------------------------------------------------------------------------
    def arquivos(self):
        self.say(f"== Arquivos de configuração -> {self.claude_dir}")
        origem = self.raiz / "claude"
        if not self.dry:
            self.claude_dir.mkdir(parents=True, exist_ok=True)
        self.copiar_arvore(origem, self.claude_dir, "claude/")
        self.copiar(origem / "settings.example.json", self.claude_dir / "settings.example.json",
                    "claude/settings.example.json")
        if (self.raiz / "painel").is_dir():
            self.say(f"== Painel da sessão -> {self.painel_dir}")
            self.copiar_arvore(self.raiz / "painel", self.painel_dir, "painel/")
            if self.so != "windows" and not self.dry:
                for s in self.painel_dir.glob("*.py"):
                    s.chmod(s.stat().st_mode | 0o111)
            if self.so == "windows":
                self.say("  aviso: a leitura de sessões do painel usa /proc, ps e ip (Linux); no Windows nativo "
                         "parte dele pode não funcionar. Para o painel completo, use o WSL.")
        if not self.feito:
            self.say("  nada mudou")
        if self.backup.is_dir():
            self.say(f"  backup do que foi substituído: {self.backup}")

    def texto_exemplo(self):
        texto = (self.raiz / "claude" / "settings.example.json").read_text(encoding="utf-8-sig")
        if self.so == "windows":  # a linha de status usa a avulsa, e o Python se chama python
            texto = texto.replace(STATUSLINE_PAINEL, STATUSLINE_AVULSA)
        return texto

    def settings(self):
        self.say("== settings.json")
        s = self.claude_dir / "settings.json"
        if not s.is_file():
            if not self.dry:
                s.write_text(self.texto_exemplo(), encoding="utf-8", newline="\n")
            elif not self.so_checar:
                self.say("  [dry-run] criar settings.json")
            self.say("  criado a partir do exemplo; troque os placeholders <...> em env")
            self.anotar(f"editar {s}: NTFY_TOPICO, NTFY_TOPICO_PERGUNTA (e OBSIDIAN_VAULT, se usar /snote)")
        elif self.a.mesclar_settings:
            self.mesclar_arquivo(s)
        else:
            self.say(f"  já existe e não foi mexido. Compare com {self.claude_dir / 'settings.example.json'} "
                     "ou rode com --mesclar-settings")
        if s.is_file():
            try:
                tem = tem_hook_rtk(json.loads(s.read_text(encoding="utf-8-sig")))
            except ValueError:
                self.anotar(f"{s} não é um JSON válido")
            else:
                if tem is None:
                    self.anotar(f"{s} tem formato inesperado em hooks: não deu para conferir o hook do rtk")
                elif not tem:
                    self.anotar("o hook do rtk não está no settings.json (rode 'rtk init -g' ou copie o bloco hooks do exemplo)")

    def mesclar_arquivo(self, s):
        try:
            atual = json.loads(s.read_text(encoding="utf-8-sig"))
            novo = mesclar(json.loads(self.texto_exemplo()), atual)
        except ValueError:
            self.anotar(f"não consegui ler {s} (JSON inválido?)")
            return
        dump = lambda o: json.dumps(o, indent=2, ensure_ascii=False) + "\n"
        if novo == atual:
            self.say("  nada a mesclar: o settings.json já tem tudo do exemplo")
            return
        self.say("  mudanças propostas:")
        for linha in difflib.unified_diff(dump(atual).splitlines(), dump(novo).splitlines(), str(s), str(s) + " (mesclado)", lineterm=""):
            self.say("    " + linha)
        if self.dry:
            self.say("  [dry-run] não gravado")
            return
        try:
            r = self.entrada(f"  Gravar a mescla em {s}? [s/N] ")
        except EOFError:
            r = "N"
        if r.strip().lower() == "s":
            self.backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, self.backup / "settings.json")
            s.write_text(dump(novo), encoding="utf-8", newline="\n")
            self.say(f"  gravado (anterior em {self.backup / 'settings.json'})")
        else:
            self.say("  mantido como estava")

    def garantir(self, bin_, obrig, como, instalar=None):
        """Instala com o comando dado se a ferramenta falta e há instalador; senão anota o que falta."""
        if self.tem(bin_):
            self.say(f"  ok       {bin_}")
            return
        if isinstance(instalar, str):  # "uvtool:pacote": instala com uv; sem uv, só sugere o pipx
            pacote = instalar.split(":", 1)[1]
            if self.tem("uv"):
                instalar = ["uv", "tool", "install", pacote]
            else:
                instalar = None
                como += f" (sem uv: pipx install {pacote})"
        if not self.so_checar and instalar and self.tem(instalar[0]):
            self.say(f"  instalando {bin_}: {' '.join(instalar)}")
            if self.rodar(instalar) and (self.dry or self.tem(bin_)):
                return
        self.say(f"  FALTA    {bin_} ({obrig})")
        self.anotar(f"{bin_} ({obrig}): {como}")

    def dependencias(self):
        self.say("== Dependências (detalhes em docs/dependencias.md)")
        for bin_, obrig, como, inst in dependencias(self.so):
            self.garantir(bin_, obrig, como, inst)
        if self.so != "windows" and not self.tem("python3"):
            self.say("  FALTA    python3 (obrigatória)")
            self.anotar(f"python3 (obrigatória): {PKG}; o painel e a statusline usam")

    def tentar(self, cmd, falta_msg, ok_msg=None):
        if self.so_checar:
            self.anotar(falta_msg)
        elif self.rodar(cmd):
            if ok_msg and not self.dry:
                self.say(ok_msg)
        else:
            self.anotar(falta_msg)

    def marketplace(self, ja, m, nome):
        if nome.lower() in ja.lower() or m.lower() in ja.lower():
            self.say(f"  ok       marketplace {nome}")
        else:
            self.tentar(["claude", "plugin", "marketplace", "add", m], f"marketplace: claude plugin marketplace add {m}")

    def plugin(self, ja, p):
        if p in ja:
            self.say(f"  ok       plugin {p}")
        else:
            self.tentar(["claude", "plugin", "install", p], f"plugin: claude plugin install {p}", f"  instalado plugin {p}")

    def claude(self):
        self.say("== Claude Code")
        if not self.tem("claude"):
            self.anotar("claude (obrigatória): https://docs.claude.com/claude-code — rode este script de novo depois")
            self.say("  FALTA    claude: pulando plugins e MCP")
            return
        self.say("  ok       claude")
        if self.tem("serena"):
            if self.ok(["claude", "mcp", "get", "serena"]):
                self.say("  ok       MCP serena")
            else:
                self.tentar(["claude"] + MCP_SERENA, "MCP serena: claude " + " ".join(MCP_SERENA))
        if self.a.sem_plugins:
            return
        ja_mp = self.ler(["claude", "plugin", "marketplace", "list"])
        ja_pl = self.ler(["claude", "plugin", "list"])
        for m in MARKETPLACES:
            self.marketplace(ja_mp, m, m.split("/")[-1])
        for p in PLUGINS:
            self.plugin(ja_pl, p)
        mods = self.claude_dir / "mods"  # mods de interface do repositório, marketplace local
        if (mods / ".claude-plugin").is_dir() or self.dry:
            self.marketplace(ja_mp, str(mods), MODS_MP)
            for p in MODS_PLUGINS:
                self.plugin(ja_pl, p)

    def resumo(self):
        self.say("")
        if not self.falta:
            self.say("Tudo certo. Abra uma sessão nova do Claude Code para carregar a configuração.")
        else:
            self.say(f"Falta fazer ({len(self.falta)}):")
            for f in self.falta:
                self.say(f"  - {f}")
            self.say("Rode python3 install.py de novo depois: o que já está certo é pulado.")
        self.say("Skills de terceiros (caveman, find-skills etc.) não vêm neste repositório: veja docs/dependencias.md.")

    def mostrar_orcamento(self):
        for base in ((self.raiz / "claude") if self.dry else self.claude_dir, self.raiz / "claude"):
            script = base / "scripts" / "orcamento_contexto.py"
            if script.is_file():
                break
        else:
            return
        self.say("")
        self.say("== Orçamento de contexto (orcamento_contexto.py)")
        env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home), PYTHONIOENCODING="utf-8")
        try:
            r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, env=env, timeout=120,
                               encoding="utf-8", errors="replace")
            self.say((r.stdout + r.stderr).rstrip())
        except (OSError, subprocess.SubprocessError) as e:
            self.say(f"  não consegui rodar: {e}")

    def executar(self):
        self.arquivos()
        self.settings()
        self.dependencias()
        self.claude()
        self.resumo()
        if self.orcamento:
            self.mostrar_orcamento()
        return 0


def main(argv=None, **kw):
    if not python_ok():
        print(f"Python {sys.version_info[0]}.{sys.version_info[1]} é antigo: o install.py precisa do 3.9 ou mais novo.", file=sys.stderr)
        return 1
    p = argparse.ArgumentParser(prog="install.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for f in ("--dry-run", "--so-checar", "--sem-plugins", "--mesclar-settings"):
        p.add_argument(f, action="store_true")
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    return Instalador(args, **kw).executar()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
