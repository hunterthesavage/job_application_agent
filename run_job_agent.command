#!/usr/bin/env bash
set -euo pipefail

cd /Users/hunter/job_agent

if [ ! -d ".venv" ]; then
  echo "Virtual environment not found at /Users/hunter/job_agent/.venv"
  read -r -p "Press Enter to close..."
  exit 1
fi

source .venv/bin/activate

python -c "import streamlit" >/dev/null 2>&1 || {
  echo "Streamlit is not installed in the virtual environment."
  read -r -p "Press Enter to close..."
  exit 1
}

open "http://localhost:8501" >/dev/null 2>&1 || true
streamlit run app.py
