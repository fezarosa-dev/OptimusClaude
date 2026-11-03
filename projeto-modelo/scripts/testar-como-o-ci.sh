#!/usr/bin/env bash
# Roda na máquina o que o CI rodaria para o que mudou, pelo MESMO mapa do CI (scripts/o_que_testar.py).
# Serve para juntar na dev (que não roda CI) e para preparar o PR para a main sem o PR ser o primeiro lugar
# onde um teste roda.
#
#   scripts/testar-como-o-ci.sh [base]             # base padrão: dev. O diff base...HEAD, mais o que não foi
#                                                  # commitado e os arquivos novos não rastreados
#   ARQUIVOS=lista.txt scripts/testar-como-o-ci.sh # só estes arquivos (um por linha): a volta depois de um conserto
#   EXIGIR_TUDO=1 scripts/testar-como-o-ci.sh      # todas as verificações; PULADO também reprova (antes do PR)
#   SO_DECIDIR=1 scripts/testar-como-o-ci.sh       # só mostra os arquivos e os passos; não roda nada
#   REGISTRO=0 scripts/testar-como-o-ci.sh         # não grava o registro da rodada (o CI usa)
#
# Não para na primeira falha: roda todos os passos e marca OK, FALHOU ou PULADO (programa que falta).
# Cada rodada deixa um resumo em registros/baterias/ (data, branch, commit, árvore, passos, duração e o sha256 do
# log) e o log completo comprimido FORA do repositório, em ${REGISTROS_FORA:-~/.local/share/registros-de-garantia}.
# Sai com 1 se algo falhar (ou, com EXIGIR_TUDO=1, se algo ficar PULADO).
set -uo pipefail

RAIZ=$(git rev-parse --show-toplevel) || { echo "não é um repositório git" >&2; exit 2; }
cd "$RAIZ" || exit 2
BASE=${1:-dev}
DECIDIR=(python3 -I scripts/o_que_testar.py)

# --- o que mudou e o que roda
if [[ ${EXIGIR_TUDO:-0} == 1 ]]; then
  MUDADOS=()
  mapfile -t PASSOS < <("${DECIDIR[@]}" --tudo)
else
  if [[ -n ${ARQUIVOS:-} ]]; then
    mapfile -t MUDADOS < <(grep -v '^[[:space:]]*$' "$ARQUIVOS")
  else
    git rev-parse --verify --quiet "$BASE^{commit}" >/dev/null || { echo "base '$BASE' não existe (git fetch?)" >&2; exit 2; }
    mapfile -d '' -t MUDADOS < <({ git diff -z --name-only --no-renames "$BASE...HEAD"
                                   git diff -z --name-only --no-renames HEAD
                                   git ls-files -z --others --exclude-standard; } | sort -zu)
  fi
  mapfile -t PASSOS < <("${DECIDIR[@]}" "${MUDADOS[@]}")
fi

if [[ ${SO_DECIDIR:-0} == 1 ]]; then
  echo "Arquivos (${#MUDADOS[@]}):"; printf '  %s\n' "${MUDADOS[@]}"
  echo "Passos:"; printf '  %s\n' "${PASSOS[@]}"
  exit 0
fi

# --- rodar
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
RESULTADOS=$TMP/resultados.tsv
LOG=$TMP/bateria.log
: > "$RESULTADOS"
INICIO=$(date +%s)

rodar() {
  local passo programas comando falta p
  for passo in "${PASSOS[@]}"; do
    IFS=$'\t' read -r programas comando < <("${DECIDIR[@]}" --mostrar "$passo")
    falta=""
    for p in $programas; do command -v "$p" >/dev/null 2>&1 || falta+=" $p"; done
    if [[ -n $falta ]]; then
      printf '%s\tPULADO (falta:%s)\n' "$passo" "$falta" >> "$RESULTADOS"
      echo "== $passo: PULADO, falta:$falta"
      continue
    fi
    echo "== $passo: $comando"
    if bash -c "$comando"; then
      printf '%s\tOK\n' "$passo" >> "$RESULTADOS"
    else
      printf '%s\tFALHOU\n' "$passo" >> "$RESULTADOS"
    fi
  done
}

registrar() {  # $1: VERDE, VERMELHA ou INTERROMPIDA
  [[ ${REGISTRO:-1} == 0 ]] && return
  local quando nome branch fora sujo novos
  quando=$(date +%Y-%m-%dT%H:%M:%S%z)
  branch=$(git rev-parse --abbrev-ref HEAD)
  nome="$(date +%Y-%m-%d-%H%M%S)-${branch//[^A-Za-z0-9._-]/-}"
  fora="${REGISTROS_FORA:-$HOME/.local/share/registros-de-garantia}/$(basename "$RAIZ")/baterias"
  mkdir -p "$fora" registros/baterias
  gzip -c "$LOG" > "$fora/$nome.log.gz"
  if [[ -n $(git status --porcelain -- . ':(exclude)registros') ]]; then
    novos=$(git ls-files --others --exclude-standard -- . ':(exclude)registros' | wc -l)
    sujo="sim (sha256 do git diff: $(git diff --no-ext-diff --no-color --binary HEAD -- . ':(exclude)registros' | sha256sum | cut -d' ' -f1); arquivos novos não rastreados: $novos)"
  else
    sujo="não"
  fi
  {
    echo "# Bateria $nome"
    echo
    echo "- **Data:** $quando"
    echo "- **Branch:** \`$branch\`"
    echo "- **Commit:** \`$(git rev-parse HEAD)\`"
    echo "- **Árvore (hash):** \`$(git rev-parse 'HEAD^{tree}')\`"
    echo "- **Mudança não commitada:** $sujo"
    echo "- **Base:** \`$BASE\` · **EXIGIR_TUDO:** ${EXIGIR_TUDO:-0} · **Arquivos no diff:** ${#MUDADOS[@]}"
    echo "- **Resultado:** $1"
    echo "- **Duração:** $(( $(date +%s) - INICIO )) s"
    echo "- **Log completo:** sha256 \`$(sha256sum "$fora/$nome.log.gz" | cut -d' ' -f1)\`, fora do repositório (\`${fora/#$HOME/~}/$nome.log.gz\`)"
    echo
    echo "| Passo | Resultado |"
    echo "|---|---|"
    while IFS=$'\t' read -r passo resultado; do echo "| $passo | $resultado |"; done < "$RESULTADOS"
  } > "registros/baterias/$nome.md"
  echo "registro: registros/baterias/$nome.md"
}

trap 'registrar INTERROMPIDA; exit 130' INT TERM
rodar 2>&1 | tee "$LOG"
trap - INT TERM

echo
echo "Resumo:"
column -t -s $'\t' "$RESULTADOS" 2>/dev/null || cat "$RESULTADOS"
if grep -q $'\tFALHOU' "$RESULTADOS" || { [[ ${EXIGIR_TUDO:-0} == 1 ]] && grep -q $'\tPULADO' "$RESULTADOS"; }; then
  registrar VERMELHA
  echo "VERMELHA: não junte."
  exit 1
fi
registrar VERDE
echo "VERDE."
