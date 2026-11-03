#!/usr/bin/env bash
# Sobe o painel em segundo plano e diz as URLs: a do PC (sem chave) e a do celular na mesma rede (com a chave).
cd "$(dirname "$0")" || exit 1
[ -f config.json ] || cp config.example.json config.json  # primeira vez sem o ativar.py
PORTA=${PORTA:-$(python3 -c 'import json;print(json.load(open("config.json"))["porta"])')}
no_ar() { curl -sf -m 2 "http://127.0.0.1:$PORTA/api/estado" | grep -q gerado_em; }
if no_ar; then
  echo "já no ar"
else
  PORTA=$PORTA nohup python3 servidor.py >servidor.log 2>&1 &
  echo $! > servidor.pid
  for _ in 1 2 3 4 5 6 7 8 9 10; do sleep 0.5; no_ar && break; done
  if ! no_ar; then echo "o servidor não subiu (porta $PORTA ocupada?):" >&2; tail -n 10 servidor.log >&2; exit 1; fi
fi
echo "PC:      http://127.0.0.1:$PORTA   (parar: kill \$(cat $(pwd)/servidor.pid))"
if [ ! -s chave.txt ]; then echo "celular: este servidor é de uma versão sem chave; pare e rode de novo"; exit 0; fi
ips=$(ip -4 -o addr | python3 -c 'import sys,analisadores as a;print(" ".join(a.ips_da_rede(sys.stdin.read())))')
for ip in $ips; do echo "celular: http://$ip:$PORTA/?chave=$(cat chave.txt)"; done
[ -n "$ips" ] || echo "celular: nenhum IP de rede (enp/wlp/eth/wl) encontrado"
