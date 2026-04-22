#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$REPO_DIR"

export PATH="/opt/homebrew/bin:$PATH"

exec .venv/bin/python scripts/deploy/run_api.py
