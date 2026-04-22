#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$REPO_DIR"

export PATH="/opt/homebrew/bin:$PATH"

# Run uvicorn inside a decrypted dotenv environment without shell eval.
exec sops exec-env --input-type dotenv .env.enc \
  '.venv/bin/uvicorn api.src.main:app --host 127.0.0.1 --port 8000'
