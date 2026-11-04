#!/usr/bin/env python3
"""Espera uma resposta dada pelo painel, imprime 'RESPOSTA <json>' e a move para entregues/. Uma por vez, a mais antiga.

A sessão do Claude roda isto em segundo plano; quando sai, aplica a resposta e roda de novo.
Uso: python3 esperar_resposta.py        (INTERVALO=5 segundos entre as olhadas)
"""
import glob
import os
import sys
import time

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "respostas")
PEND, ENTR = os.path.join(BASE, "pendentes"), os.path.join(BASE, "entregues")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows: a resposta com acento não pode quebrar depois de movida
    os.makedirs(PEND, exist_ok=True)
    os.makedirs(ENTR, exist_ok=True)
    intervalo = float(os.environ.get("INTERVALO", 5))
    while True:
        # nome ordenado = ordem de chegada; o servidor só põe arquivo aqui pelo rename (*.json.tmp não casa)
        for f in sorted(glob.glob(os.path.join(PEND, "*.json"))):
            destino = os.path.join(ENTR, os.path.basename(f))
            os.replace(f, destino)
            with open(destino, encoding="utf-8") as fh:
                print("RESPOSTA " + fh.read().replace("\n", ""), flush=True)
            return 0
        time.sleep(intervalo)


if __name__ == "__main__":
    sys.exit(main())
