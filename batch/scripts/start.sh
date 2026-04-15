#!/bin/bash
# 배치 수동 실행 스크립트
# 사용법: bash batch/scripts/start.sh

BATCH_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BATCH_DIR"

source .venv/bin/activate
python3.11 -m src.batch
