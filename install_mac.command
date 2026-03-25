#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

chmod +x install_mac.sh run_app.sh
exec ./install_mac.sh
