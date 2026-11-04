#!/usr/bin/env python3
"""Sobe o painel em segundo plano e diz as URLs: a do PC (sem chave) e a do celular na mesma rede (com a chave).

Uso: python3 iniciar.py        (PORTA=8765 python3 iniciar.py troca a porta)
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
os.chdir(AQUI)
sys.path.insert(0, AQUI)
import analisadores  # noqa: E402


def no_ar(porta):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/estado", timeout=2) as r:
            return "gerado_em" in r.read().decode("utf-8", "replace")
    except Exception:
        return False


def ips():
    if shutil.which("ip"):
        saida = subprocess.run(["ip", "-4", "-o", "addr"], capture_output=True, text=True).stdout
        return analisadores.ips_da_rede(saida)
    try:  # sem `ip` (Windows/macOS): o IP da rota de saída; UDP não manda nada
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return [s.getsockname()[0]]
    except OSError:
        return []


def _comando_parar():
    try:
        with open(os.path.join(AQUI, "servidor.pid")) as f:
            pid = f.read().strip()
    except OSError:
        return "servidor.pid não encontrado"
    return f"taskkill /PID {pid}" if os.name == "nt" else f"kill {pid}"


def main():
    if not os.path.exists("config.json"):
        shutil.copy("config.example.json", "config.json")  # primeira vez sem o ativar.py
    porta = os.environ.get("PORTA")
    if not porta:
        with open("config.json", encoding="utf-8") as f:
            porta = str(json.load(f)["porta"])
    if no_ar(porta):
        print("já no ar")
    else:
        extra = {"creationflags": 0x00000008 | 0x00000200} if os.name == "nt" else {"start_new_session": True}
        with open("servidor.log", "w") as log:
            p = subprocess.Popen([sys.executable, "servidor.py"], stdout=log, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, env={**os.environ, "PORTA": porta}, **extra)
        with open("servidor.pid", "w") as f:
            f.write(str(p.pid) + "\n")
        for _ in range(10):
            time.sleep(0.5)
            if no_ar(porta):
                break
        if not no_ar(porta):
            print(f"o servidor não subiu (porta {porta} ocupada?):", file=sys.stderr)
            with open("servidor.log", encoding="utf-8", errors="replace") as f:
                print("".join(f.readlines()[-10:]), file=sys.stderr, end="")
            return 1
    print(f"PC:      http://127.0.0.1:{porta}   (parar: {_comando_parar()})")
    if not os.path.isfile("chave.txt") or os.path.getsize("chave.txt") == 0:
        print("celular: este servidor é de uma versão sem chave; pare e rode de novo")
        return 0
    with open("chave.txt", encoding="utf-8") as f:
        chave = f.read().strip()
    lista = ips()
    for ip in lista:
        print(f"celular: http://{ip}:{porta}/?chave={chave}")
    if not lista:
        print("celular: nenhum IP de rede (enp/wlp/eth/wl) encontrado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
