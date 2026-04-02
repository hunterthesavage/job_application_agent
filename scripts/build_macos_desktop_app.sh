#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d .venv ]; then
  echo "Virtual environment not found. Run ./install_mac.sh first."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if ! python -c "import PyInstaller" >/dev/null 2>&1; then
  echo "==> Installing PyInstaller into the local virtual environment"
  pip install pyinstaller
fi

echo "==> Cleaning previous desktop app build artifacts"
rm -rf build dist

echo "==> Building macOS desktop app bundle"
pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "Job Application Agent" \
  --collect-all streamlit \
  --collect-all pywebview \
  --add-data "app.py:." \
  --add-data "services:services" \
  --add-data "views:views" \
  --add-data "ui:ui" \
  --add-data "src:src" \
  --add-data "config.py:." \
  desktop_app.py

echo
echo "Desktop app bundle created at:"
echo "dist/Job Application Agent.app"
