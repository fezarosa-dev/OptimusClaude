#!/usr/bin/env bash
# Instala a configuração do Claude Code deste repositório.
#   claude/*  -> ~/.claude          (com backup do que já existe e for diferente)
#   painel/   -> ~/painel-da-sessao (idem; arquivos de estado do painel não são tocados)
# Depois checa (e instala, quando há instalador seguro) as dependências e os plugins.
# Idempotente: rodar de novo só copia o que mudou.
#
# Uso: ./install.sh [--dry-run] [--so-checar] [--sem-plugins] [--mesclar-settings]
#   --dry-run           mostra o que faria, sem mudar nada
#   --so-checar         não grava nada (nem cópia, nem backup, nem settings, nem instalação): só confere e
#                       lista o que falta e os arquivos que seriam copiados
#   --sem-plugins       pula marketplaces e plugins do Claude Code
#   --mesclar-settings  mescla settings.example.json no ~/.claude/settings.json existente (precisa de jq;
#                       objetos mesclados, arrays juntados sem duplicata e sem reordenar (os do usuário primeiro),
#                       escalar do usuário vence; pede confirmação)
set -uo pipefail

DRY=0; SO_CHECAR=0; SEM_PLUGINS=0; MESCLAR=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --so-checar) SO_CHECAR=1; DRY=1 ;;  # conferir = simulação silenciosa (run não imprime nem executa)
    --sem-plugins) SEM_PLUGINS=1 ;;
    --mesclar-settings) MESCLAR=1 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $a (veja --help)" >&2; exit 2 ;;
  esac
done

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
PAINEL_DIR="$HOME/painel-da-sessao"
BACKUP="$CLAUDE_DIR/backups/optimusclaude-$(date +%Y%m%d-%H%M%S)"
FALTA=()   # o que o usuário ainda precisa fazer
FEITO=0

say()  { printf '%s\n' "$*"; }
run()  { if [ "$SO_CHECAR" = 1 ]; then :; elif [ "$DRY" = 1 ]; then say "  [dry-run] $*"; else "$@"; fi; }
tem()  { command -v "$1" >/dev/null 2>&1; }
falta() { FALTA+=("$1"); }

# copia um arquivo; se o destino existe e é diferente, guarda o antigo no backup
copiar() {
  local src="$1" dst="$2" rel="$3"
  if [ -f "$dst" ] && cmp -s "$src" "$dst"; then return 0; fi
  if [ -e "$dst" ]; then
    run mkdir -p "$(dirname "$BACKUP/$rel")"
    run cp -p "$dst" "$BACKUP/$rel"
  fi
  run mkdir -p "$(dirname "$dst")"
  run cp -p "$src" "$dst"
  say "  ${rel}"
  FEITO=$((FEITO + 1))
}

copiar_arvore() {
  local origem="$1" destino="$2" prefixo="$3"; shift 3
  local f rel
  while IFS= read -r -d '' f; do
    rel="${f#"$origem"/}"
    copiar "$f" "$destino/$rel" "$prefixo$rel"
  done < <(find "$origem" -type f "$@" -print0)
}

say "== Arquivos de configuração -> $CLAUDE_DIR"
[ "$DRY" = 1 ] || mkdir -p "$CLAUDE_DIR"
copiar_arvore "$RAIZ/claude" "$CLAUDE_DIR" "claude/" ! -name settings.example.json ! -name '*.pyc' ! -path '*/__pycache__/*'
copiar "$RAIZ/claude/settings.example.json" "$CLAUDE_DIR/settings.example.json" "claude/settings.example.json"

if [ -d "$RAIZ/painel" ]; then
  say "== Painel da sessão -> $PAINEL_DIR"
  copiar_arvore "$RAIZ/painel" "$PAINEL_DIR" "painel/" ! -name '*.pyc' ! -path '*/__pycache__/*'
  for s in "$PAINEL_DIR"/*.sh; do [ -f "$s" ] && [ ! -x "$s" ] && run chmod +x "$s"; done
fi
[ "$FEITO" = 0 ] && say "  nada mudou"
[ -d "$BACKUP" ] && say "  backup do que foi substituído: $BACKUP"

say "== settings.json"
SETTINGS="$CLAUDE_DIR/settings.json"
if [ ! -f "$SETTINGS" ]; then
  run cp "$RAIZ/claude/settings.example.json" "$SETTINGS"
  say "  criado a partir do exemplo; troque os placeholders <...> em env"
  falta "editar $SETTINGS: NTFY_TOPICO, NTFY_TOPICO_PERGUNTA (e OBSIDIAN_VAULT, se usar /snote)"
elif [ "$MESCLAR" = 1 ]; then
  if ! tem jq; then
    falta "instalar jq para usar --mesclar-settings (ou mesclar à mão com $CLAUDE_DIR/settings.example.json)"
  else
    NOVO="$(mktemp)"
    # exemplo como base, usuário por cima: nada do usuário se perde
    # objetos mesclados em profundidade (chaves do usuário primeiro, na ordem dele), escalar do usuário vence;
    # arrays: os do usuário na ordem dele, depois os do exemplo que faltam (por valor), sem ordenar (unique ordenaria hooks/permissions)
    JQ_MESCLA='def m($a;$b): if ($a|type)=="object" and ($b|type)=="object" then reduce ((($b|keys_unsorted)+($a|keys_unsorted))[]) as $k ({}; if has($k) then . else .[$k] = (if ($a|has($k)) and ($b|has($k)) then m($a[$k];$b[$k]) elif ($b|has($k)) then $b[$k] else $a[$k] end) end) elif ($a|type)=="array" and ($b|type)=="array" then reduce $a[] as $x ($b; if any(.[]; . == $x) then . else . + [$x] end) else $b end; m(.[0];.[1])'
    if jq -s "$JQ_MESCLA" "$RAIZ/claude/settings.example.json" "$SETTINGS" > "$NOVO"; then
      say "  mudanças propostas:"; diff -u "$SETTINGS" "$NOVO" | sed 's/^/    /' || true
      if [ "$DRY" = 1 ]; then say "  [dry-run] não gravado"
      else
        read -r -p "  Gravar a mescla em $SETTINGS? [s/N] " r
        if [ "${r:-N}" = s ] || [ "${r:-N}" = S ]; then
          mkdir -p "$BACKUP"; cp -p "$SETTINGS" "$BACKUP/settings.json"; cp "$NOVO" "$SETTINGS"
          say "  gravado (anterior em $BACKUP/settings.json)"
        else say "  mantido como estava"; fi
      fi
    else falta "jq não conseguiu ler $SETTINGS (JSON inválido?)"; fi
    rm -f "$NOVO"
  fi
else
  say "  já existe e não foi mexido. Compare com $CLAUDE_DIR/settings.example.json ou rode com --mesclar-settings"
fi
if [ -f "$SETTINGS" ] && tem jq && ! jq -e '[.hooks.PreToolUse[]?.hooks[]?.command] | any(test("rtk hook"))' "$SETTINGS" >/dev/null 2>&1; then
  falta "o hook do rtk não está no settings.json (rode 'rtk init -g' ou copie o bloco hooks do exemplo)"
fi

# instala com o comando dado se a ferramenta falta e há instalador; senão anota o que falta
garantir() {
  local bin="$1" obrig="$2" como="$3"; shift 3
  if tem "$bin"; then say "  ok       $bin"; return 0; fi
  if [ "$SO_CHECAR" = 0 ] && [ "$#" -gt 0 ] && tem "$1"; then
    say "  instalando $bin: $*"
    if run "$@" && { [ "$DRY" = 1 ] || tem "$bin"; }; then return 0; fi
  fi
  say "  FALTA    $bin ($obrig)"
  falta "$bin ($obrig): $como"
}

say "== Dependências (detalhes em docs/dependencias.md)"
garantir git     obrigatória "instale pelo gerenciador de pacotes do sistema"
garantir node    obrigatória "https://nodejs.org (ou fnm/nvm); precisa para context-mode e caveman"
garantir python3 obrigatória "instale pelo gerenciador de pacotes do sistema; o painel e a statusline usam"
garantir uv      obrigatória "curl -LsSf https://astral.sh/uv/install.sh | sh"
garantir rtk     obrigatória "veja https://github.com/rtk-ai/rtk (script de instalação ou cargo); depois 'rtk init -g'"
garantir caveman obrigatória "npm i -g @caveman-ai/cli; depois 'caveman hooks install claude'" npm i -g @caveman-ai/cli
garantir serena  obrigatória "uv tool install serena-agent" uv tool install serena-agent
garantir ccc     obrigatória "uv tool install cocoindex-code" uv tool install cocoindex-code
garantir gh      recomendada "https://cli.github.com"
garantir jq      recomendada "instale pelo gerenciador de pacotes do sistema"
garantir gitleaks recomendada "https://github.com/gitleaks/gitleaks (binário da release ou gerenciador de pacotes)"
garantir semgrep opcional   "uv tool install semgrep" uv tool install semgrep
garantir curl    recomendada "instale pelo gerenciador de pacotes do sistema; os avisos do ntfy usam"

say "== Claude Code"
if ! tem claude; then
  falta "claude (obrigatória): https://docs.claude.com/claude-code — rode este script de novo depois"
  say "  FALTA    claude: pulando plugins e MCP"
else
  say "  ok       claude"
  if tem serena; then
    if claude mcp get serena >/dev/null 2>&1; then say "  ok       MCP serena"
    elif [ "$SO_CHECAR" = 0 ]; then
      run claude mcp add -s user serena -- serena start-mcp-server --context claude-code --project-from-cwd \
        || falta "MCP serena: claude mcp add -s user serena -- serena start-mcp-server --context claude-code --project-from-cwd"
    else falta "MCP serena: claude mcp add -s user serena -- serena start-mcp-server --context claude-code --project-from-cwd"; fi
  fi

  if [ "$SEM_PLUGINS" = 0 ]; then
    MARKETPLACES=(anthropics/claude-plugins-official mksglu/context-mode DietrichGebert/ponytail trailofbits/skills guillaumemeyer/watermarks-remover latent-spaces/brag)
    PLUGINS=(superpowers@claude-plugins-official claude-code-setup@claude-plugins-official skill-creator@claude-plugins-official
             code-simplifier@claude-plugins-official claude-security@claude-plugins-official security-guidance@claude-plugins-official
             pyright-lsp@claude-plugins-official typescript-lsp@claude-plugins-official context-mode@context-mode ponytail@ponytail
             insecure-defaults@trailofbits watermarks-remover@watermarks-remover brag@brag)
    JA_MP="$(claude plugin marketplace list 2>/dev/null || true)"
    JA_PL="$(claude plugin list 2>/dev/null || true)"
    for m in "${MARKETPLACES[@]}"; do
      if grep -qiF "${m#*/}" <<<"$JA_MP" || grep -qiF "$m" <<<"$JA_MP"; then say "  ok       marketplace $m"
      elif [ "$SO_CHECAR" = 0 ]; then run claude plugin marketplace add "$m" >/dev/null 2>&1 || falta "marketplace: claude plugin marketplace add $m"
      else falta "marketplace: claude plugin marketplace add $m"; fi
    done
    for p in "${PLUGINS[@]}"; do
      if grep -qF "$p" <<<"$JA_PL"; then say "  ok       plugin $p"
      elif [ "$SO_CHECAR" = 0 ]; then run claude plugin install "$p" >/dev/null 2>&1 && say "  instalado plugin $p" || falta "plugin: claude plugin install $p"
      else falta "plugin: claude plugin install $p"; fi
    done
    # mods de interface do repositório (claude/mods -> ~/.claude/mods), marketplace local
    MODS_MP="optimus-mods"
    if [ -d "$CLAUDE_DIR/mods/.claude-plugin" ] || [ "$DRY" = 1 ]; then
      if grep -qiF "$MODS_MP" <<<"$JA_MP"; then say "  ok       marketplace $MODS_MP"
      elif [ "$SO_CHECAR" = 0 ]; then run claude plugin marketplace add "$CLAUDE_DIR/mods" >/dev/null 2>&1 || falta "marketplace: claude plugin marketplace add $CLAUDE_DIR/mods"
      else falta "marketplace: claude plugin marketplace add $CLAUDE_DIR/mods"; fi
      for p in status-bar@$MODS_MP painel-agentes@$MODS_MP; do
        if grep -qF "$p" <<<"$JA_PL"; then say "  ok       plugin $p"
        elif [ "$SO_CHECAR" = 0 ]; then run claude plugin install "$p" >/dev/null 2>&1 && say "  instalado plugin $p" || falta "plugin: claude plugin install $p"
        else falta "plugin: claude plugin install $p"; fi
      done
    fi
  fi
fi

say ""
if [ "${#FALTA[@]}" = 0 ]; then
  say "Tudo certo. Abra uma sessão nova do Claude Code para carregar a configuração."
else
  say "Falta fazer (${#FALTA[@]}):"
  for f in "${FALTA[@]}"; do say "  - $f"; done
  say "Rode ./install.sh de novo depois: o que já está certo é pulado."
fi
say "Skills de terceiros (caveman, find-skills etc.) não vêm neste repositório: veja docs/dependencias.md."
