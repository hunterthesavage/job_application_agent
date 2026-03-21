#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

mkdir -p data backups logs

echo ""
echo "Setup complete."
echo "Run the app with: streamlit run app.py"
echo "Run tests with: python -m pytest"
