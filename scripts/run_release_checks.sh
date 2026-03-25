#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  echo "ERROR: .venv not found in $ROOT_DIR"
  echo "Run ./install_mac.sh first."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Running Job Application Agent release checks..."
python -m pytest -q \
  tests/test_settings.py \
  tests/test_job_store.py \
  tests/test_ingestion.py \
  tests/test_openai_key.py \
  tests/test_health.py \
  tests/test_status.py \
  tests/test_sqlite_actions.py \
  tests/test_smoke_regression.py \
  tests/test_ui_components.py \
  tests/test_ai_job_scrub.py \
  tests/test_pipeline_view_logic.py

echo ""
echo "Release checks passed."

