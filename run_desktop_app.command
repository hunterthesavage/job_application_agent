#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
chmod +x run_desktop_app.sh
exec ./run_desktop_app.sh
