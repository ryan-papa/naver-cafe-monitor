#!/usr/bin/env bash
# install_cron.sh — 30분마다 batch.py를 실행하는 crontab 등록
#
# 사용법: bash scripts/install_cron.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/batch.log"
VENV_DIR="$PROJECT_DIR/.venv"

# 로그 디렉터리 생성
mkdir -p "$LOG_DIR"

# venv 존재 확인
if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: .venv 디렉터리가 없습니다. 먼저 가상환경을 생성하세요."
    echo "  python -m venv .venv && source .venv/bin/activate && pip install -e ."
    exit 1
fi

# cron 작업 정의
CRON_CMD="*/30 * * * * cd $PROJECT_DIR && $VENV_DIR/bin/python -m src.batch >> $LOG_FILE 2>&1"
CRON_MARKER="# naver-cafe-monitor batch"

# 기존 등록 여부 확인 후 설치
EXISTING=$(crontab -l 2>/dev/null || true)

if echo "$EXISTING" | grep -q "naver-cafe-monitor batch"; then
    echo "기존 cron 작업을 교체합니다..."
    CLEANED=$(echo "$EXISTING" | grep -v "naver-cafe-monitor batch")
    echo "$CLEANED" | crontab -
fi

# 새 cron 추가
(crontab -l 2>/dev/null || true; echo "$CRON_CMD $CRON_MARKER") | crontab -

echo "cron 설치 완료!"
echo ""
echo "등록된 작업:"
crontab -l | grep "naver-cafe-monitor"
echo ""
echo "로그 확인: tail -f $LOG_FILE"
echo "제거: crontab -e 에서 naver-cafe-monitor 행 삭제"
