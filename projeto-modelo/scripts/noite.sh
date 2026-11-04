#!/usr/bin/env bash
# Modo noturno: roda a fila do TASKS.md sozinho até esvaziar, uma tarefa por sessão nova do Claude (contexto limpo).
#
# Uso (na raiz do projeto, na dev atualizada):  scripts/noite.sh
#   NOITE_MODELO=opus   modelo da sessão orquestradora (padrão: o do seu settings)
#   NOITE_PROMPT=...    arquivo com um prompt próprio no lugar do padrão
#
# Cada rodada abre `claude -p --dangerously-skip-permissions` (tudo liberado) com uma guarda que só vale esta noite
# (scripts/noite_guarda.py, passada por --settings): sem push, sem PR, sem tocar na main, sem reset --hard. Os hooks
# do seu ~/.claude continuam valendo. A sessão pega a primeira tarefa `aprovada` sem dúvida aberta, faz pelo fluxo do
# método (worktree, TDD por subagente, revisão, correção até 3 rodadas, bateria), junta na dev LOCAL e atualiza o
# TASKS.md. Tarefa que não fica verde vai para o duvidas.md e a fila segue. Sem limite de tarefas nem de horas: para
# quando a fila esvazia, quando a mesma tarefa volta duas vezes seguidas ou depois de 3 falhas seguidas do claude.
# No fim manda o resumo para o ntfy (NTFY_TOPICO), se estiver definido. Log em .noite/AAAA-MM-DD.log.
set -uo pipefail

RAIZ="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "rode dentro do repositório" >&2; exit 2; }
cd "$RAIZ"
[ -f TASKS.md ] || { echo "sem TASKS.md na raiz: o modo noturno lê a fila dele" >&2; exit 2; }
command -v claude >/dev/null || { echo "claude não encontrado no PATH" >&2; exit 2; }
[ "$(git branch --show-current)" = dev ] || { echo "comece na dev (git switch dev && git pull)" >&2; exit 2; }
git diff --quiet && git diff --cached --quiet || { echo "a dev tem mudança não commitada: commite ou guarde antes" >&2; exit 2; }

mkdir -p .noite
grep -qxF '.noite/' .gitignore 2>/dev/null || echo '.noite/' >> .gitignore
LOG=".noite/$(date +%F).log"
GUARDA="$RAIZ/scripts/noite_guarda.py"
CONFIG="$(mktemp)"; trap 'rm -f "$CONFIG"' EXIT
printf '{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"python3 \\"%s\\""}]}]}}' "$GUARDA" > "$CONFIG"

PROMPT_PADRAO='Modo noturno do OptimusClaude. Você está sozinho: o usuário está dormindo, não pergunte nada a ele e não use a skill grilling. Siga o CLAUDE.md do projeto e o global.
1. Leia TASKS.md e duvidas.md. Escolha a PRIMEIRA tarefa com estado `aprovada` (de cima para baixo) que não tenha dúvida aberta no duvidas.md. Se não houver nenhuma, responda só a linha: NOITE_FIM
2. Marque a tarefa como `em andamento (noite)` no TASKS.md.
3. Faça a tarefa pelo fluxo do método: worktree próprio a partir da dev, implementação com TDD por subagente, revisão do diff por outro subagente, correção até 3 rodadas, bateria do que mudou (scripts/testar-como-o-ci.sh). Leia registros/padroes.md antes e junte nele as lições do revisor.
4. Verde: commit na branch da tarefa, merge --no-ff na dev LOCAL (sem push), apague o worktree, estado `feita na dev (noite, sem push)`.
5. Não ficou verde depois de 3 rodadas, ou precisa de decisão do usuário: registre no duvidas.md (o que travou, onde parou, opções com recomendação), estado `travada (noite)`, deixe a branch como está e volte para a dev.
6. Nunca: push, PR, tocar na main, reset --hard (uma guarda nega).
Termine com UMA linha, a última da resposta: NOITE_TAREFA <Tn> <feita|travada> <resumo de uma frase>'
PROMPT="$PROMPT_PADRAO"
[ -n "${NOITE_PROMPT:-}" ] && PROMPT="$(cat "$NOITE_PROMPT")"
MODELO=(); [ -n "${NOITE_MODELO:-}" ] && MODELO=(--model "$NOITE_MODELO")

say() { echo "[$(date +%T)] $*" | tee -a "$LOG"; }
feitas=(); travadas=(); anterior=""; falhas=0; motivo_fim="fila vazia"
say "início, dev em $(git rev-parse --short HEAD)"

while :; do
  saida="$(claude -p --dangerously-skip-permissions --settings "$CONFIG" "${MODELO[@]}" "$PROMPT" 2>>"$LOG")"; cod=$?
  printf '%s\n' "$saida" >> "$LOG"
  ultima="$(printf '%s\n' "$saida" | grep -E '^NOITE_(FIM|TAREFA)' | tail -1)"
  if [ $cod -ne 0 ] || [ -z "$ultima" ]; then
    falhas=$((falhas + 1)); say "rodada sem resposta válida (saída $cod), falha $falhas de 3"
    [ $falhas -ge 3 ] && { motivo_fim="3 falhas seguidas do claude (veja o log)"; break; }
    continue
  fi
  falhas=0
  [ "$ultima" = NOITE_FIM ] && break
  read -r _ tn estado resto <<<"$ultima"
  say "$tn $estado: $resto"
  [ "$tn" = "$anterior" ] && { motivo_fim="$tn voltou duas vezes seguidas"; break; }
  anterior="$tn"
  if [ "$estado" = feita ]; then feitas+=("$tn"); else travadas+=("$tn"); fi
  [ "$(git branch --show-current)" = dev ] || git switch -q dev
done

resumo="Noite: ${#feitas[@]} feita(s) ${feitas[*]:-} · ${#travadas[@]} travada(s) ${travadas[*]:-} · fim: $motivo_fim. Push da dev: você decide."
say "$resumo"
if [ -n "${NTFY_TOPICO:-}" ]; then
  curl -s -H "Title: Modo noturno terminou" -H "Tags: crescent_moon" -d "$resumo" "ntfy.sh/$NTFY_TOPICO" >/dev/null || true
fi
