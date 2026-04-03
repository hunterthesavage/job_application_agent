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

echo "==> Repairing local file permissions"
find services src views ui tests docs -type f -name "*.py" -exec chmod a+r {} + 2>/dev/null || true
for path in README.md app.py config.py requirements.txt profile_context.txt; do
  if [ -f "$path" ]; then
    chmod a+r "$path" 2>/dev/null || true
  fi
done
chmod +x install_mac.sh run_app.sh run_desktop_app.sh install_mac.command run_app.command run_desktop_app.command 2>/dev/null || true

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
chmod +x run_app.sh run_app.command run_desktop_app.sh run_desktop_app.command

echo

echo "Install complete."
echo "Start the app with: ./run_app.sh"
echo "Or double-click: run_app.command"
echo
echo "Desktop wrapper spike:"
echo "Start the native window with: ./run_desktop_app.sh"
echo "Or double-click: run_desktop_app.command"
