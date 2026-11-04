#!/usr/bin/env bash
# Embrulho: confere o Python e chama install.py (que faz o trabalho). Uso: ./install.sh [--dry-run] [--so-checar] [--sem-plugins] [--mesclar-settings]
if ! command -v python3 >/dev/null 2>&1; then
  if   command -v apt-get >/dev/null 2>&1; then c="sudo apt-get install -y python3"
  elif command -v dnf     >/dev/null 2>&1; then c="sudo dnf install -y python3"
  elif command -v pacman  >/dev/null 2>&1; then c="sudo pacman -S python"
  elif command -v zypper  >/dev/null 2>&1; then c="sudo zypper install python3"
  elif command -v brew    >/dev/null 2>&1; then c="brew install python"
  else c="instale o Python 3.9+ pelo gerenciador de pacotes do sistema"; fi
  echo "python3 não encontrado. Instale com: $c" >&2
  echo "Depois rode ./install.sh de novo." >&2
  exit 1
fi
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
  echo "O python3 daqui é anterior ao 3.9; o install.py precisa do 3.9 ou mais novo. Atualize o Python e rode de novo." >&2
  exit 1
fi
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install.py" "$@"
