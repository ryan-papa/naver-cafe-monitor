#!/bin/bash
set -euo pipefail

REPO_DIR="/Users/hose.kim/Claude/claude-projects/repositories/naver-cafe-monitor"
cd "$REPO_DIR"

export PATH="/opt/homebrew/bin:$PATH"

# Decrypt .env.enc and export all vars, then exec uvicorn
set -a
eval "$(sops -d --input-type dotenv --output-type dotenv .env.enc)"
set +a

exec .venv/bin/uvicorn api.src.main:app --host 127.0.0.1 --port 8000
