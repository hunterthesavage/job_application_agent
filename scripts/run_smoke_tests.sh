#!/bin/bash
set -e

cd /Users/hunter/job_agent

if [ ! -d ".venv" ]; then
  echo "ERROR: .venv not found in /Users/hunter/job_agent"
  exit 1
fi

source .venv/bin/activate

echo "Running Job Application Agent smoke tests..."
pytest -q \
  tests/test_settings.py \
  tests/test_job_store.py \
  tests/test_ingestion.py \
  tests/test_openai_key.py \
  tests/test_health.py \
  tests/test_status.py \
  tests/test_sqlite_actions.py \
  tests/test_smoke_regression.py

echo ""
echo "Smoke tests passed."
