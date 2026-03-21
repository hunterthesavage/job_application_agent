#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_URL="http://localhost:8501"

cd "$PROJECT_DIR"

echo "Launching Job Application Agent from:"
echo "$PROJECT_DIR"
echo ""

if [ ! -d ".venv" ]; then
  echo "Virtual environment not found at:"
  echo "$PROJECT_DIR/.venv"
  echo ""
  echo "Run ./setup.sh first, or create the venv manually."
  read -r -p "Press Enter to close..."
  exit 1
fi

source ".venv/bin/activate"

if ! python -c "import streamlit" >/dev/null 2>&1; then
  echo "Streamlit is not installed in the virtual environment."
  echo ""
  echo "Run:"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  echo ""
  read -r -p "Press Enter to close..."
  exit 1
fi

echo "Starting Streamlit..."
echo "App URL: $APP_URL"
echo ""
echo "Leave this window open while the app is running."
echo "Press Control+C in this window to stop the app."
echo ""

python -m streamlit run app.py
