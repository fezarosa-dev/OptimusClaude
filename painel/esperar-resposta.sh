#!/usr/bin/env bash
# Espera uma resposta dada pelo painel, imprime 'RESPOSTA <json>' e a move para entregues/. Uma por vez, a mais antiga.
# A sessão do Claude roda isto em segundo plano; quando sai, aplica a resposta e roda de novo.
cd "$(dirname "$0")/respostas" 2>/dev/null || { mkdir -p "$(dirname "$0")/respostas" && cd "$(dirname "$0")/respostas"; } || exit 1
mkdir -p pendentes entregues
while :; do
  for f in pendentes/*.json; do  # o glob sai em ordem de nome = ordem de chegada; o servidor só põe arquivo aqui pelo rename
    [ -e "$f" ] || break
    mv -- "$f" entregues/ || exit 1
    printf 'RESPOSTA %s\n' "$(tr -d '\n' < "entregues/${f#pendentes/}")"
    exit 0
  done
  sleep "${INTERVALO:-5}"
done
