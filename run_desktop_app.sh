#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ ! -d .venv ]; then
  echo "Virtual environment not found. Run ./install_mac.sh first."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

mkdir -p data backups logs

exec python -m services.desktop_wrapper
