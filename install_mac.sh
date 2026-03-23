#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "==> Job Application Agent macOS install"

echo "==> Checking Python 3"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required but was not found."
  exit 1
fi

echo "==> Creating virtual environment"
python3 -m venv .venv

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Upgrading pip"
python -m pip install --upgrade pip

echo "==> Installing requirements"
pip install -r requirements.txt

echo "==> Preparing local folders"
mkdir -p data backups logs .streamlit
[ -f data/.gitkeep ] || touch data/.gitkeep
[ -f backups/.gitkeep ] || touch backups/.gitkeep

if [ ! -f .streamlit/config.toml ]; then
  cat > .streamlit/config.toml <<'EOF'
[client]
toolbarMode = "minimal"
showSidebarNavigation = false

[theme]
base = "dark"
EOF
fi

echo "==> Making launcher executable"
chmod +x run_app.sh

echo

echo "Install complete."
echo "Start the app with: ./run_app.sh"
