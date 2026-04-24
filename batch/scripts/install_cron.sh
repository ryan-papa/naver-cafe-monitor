#!/usr/bin/env bash
# install_cron.sh — naver-cafe-monitor cron 엔트리 설치/제거
#
# 엔트리:
#   - batch          : 30분 주기 (`*/30 * * * *`) — 네이버 카페 크롤링 + 카톡 발송
#   - kakao-refresh  : 3시간 주기 (`15 */3 * * *`) — 카카오 access/refresh token 선제 갱신
#
# 사용법:
#   bash batch/scripts/install_cron.sh                    # batch + refresh 설치 (멱등)
#   bash batch/scripts/install_cron.sh --uninstall=batch  # batch 엔트리만 제거
#   bash batch/scripts/install_cron.sh --uninstall=refresh
#   bash batch/scripts/install_cron.sh --uninstall=all    # 모두 제거 (기본값)
#   bash batch/scripts/install_cron.sh --uninstall        # --uninstall=all 과 동일

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BATCH_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$BATCH_DIR/logs"
BATCH_LOG="$LOG_DIR/batch.log"
REFRESH_LOG="$LOG_DIR/kakao_refresh.log"
VENV_DIR="${VENV_DIR:-$BATCH_DIR/.venv}"

BATCH_MARKER="# naver-cafe-monitor batch"
REFRESH_MARKER="# naver-cafe-monitor kakao-refresh"

usage() {
    cat <<EOF
Usage: $0 [--uninstall[=refresh|batch|all]]

  (옵션 없음)          batch + refresh 엔트리 설치 (기존 중복 제거 후 재삽입, 멱등)
  --uninstall          = --uninstall=all
  --uninstall=refresh  refresh 엔트리만 제거
  --uninstall=batch    batch 엔트리만 제거
  --uninstall=all      모두 제거

환경변수:
  VENV_DIR   가상환경 경로 (기본: \$BATCH_DIR/.venv)
EOF
}

# ── 인자 파싱 ────────────────────────────────────────────────────────────────
MODE="install"
TARGET="all"
if [ $# -gt 0 ]; then
    case "$1" in
        --uninstall)
            MODE="uninstall"; TARGET="all" ;;
        --uninstall=refresh|--uninstall=batch|--uninstall=all)
            MODE="uninstall"; TARGET="${1#--uninstall=}" ;;
        --uninstall=*)
            echo "ERROR: invalid --uninstall value: ${1#--uninstall=}" >&2
            usage >&2
            exit 2 ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            usage >&2
            exit 2 ;;
    esac
fi

# ── 공통 유틸 ────────────────────────────────────────────────────────────────
current_crontab() {
    crontab -l 2>/dev/null || true
}

remove_marker() {
    local marker="$1" input="$2"
    # 마커를 포함한 라인 제거
    echo "$input" | grep -v -F "$marker" || true
}

# ── uninstall 경로 ──────────────────────────────────────────────────────────
if [ "$MODE" = "uninstall" ]; then
    CURRENT="$(current_crontab)"
    CLEANED="$CURRENT"
    case "$TARGET" in
        refresh|all)
            CLEANED="$(remove_marker "$REFRESH_MARKER" "$CLEANED")" ;;
    esac
    case "$TARGET" in
        batch|all)
            CLEANED="$(remove_marker "$BATCH_MARKER" "$CLEANED")" ;;
    esac
    if [ -z "$CLEANED" ]; then
        # 빈 crontab 등록 (crontab - 로 교체)
        printf "" | crontab -
    else
        printf "%s\n" "$CLEANED" | crontab -
    fi
    echo "제거 완료: target=$TARGET"
    echo ""
    echo "현재 등록된 작업:"
    current_crontab | grep "naver-cafe-monitor" || echo "  (없음)"
    exit 0
fi

# ── install 경로 ────────────────────────────────────────────────────────────
mkdir -p "$LOG_DIR"

if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: venv 디렉터리가 없습니다: $VENV_DIR" >&2
    echo "  python -m venv .venv && source .venv/bin/activate && pip install -e ." >&2
    exit 1
fi

BATCH_CMD="*/30 * * * * cd $BATCH_DIR && $VENV_DIR/bin/python -m src.batch >> $BATCH_LOG 2>&1 $BATCH_MARKER"
REFRESH_CMD="15 */3 * * * cd $BATCH_DIR && $VENV_DIR/bin/python -m src.kakao_refresh >> $REFRESH_LOG 2>&1 $REFRESH_MARKER"

# 기존 엔트리 제거(멱등) 후 추가
CURRENT="$(current_crontab)"
CLEANED="$(remove_marker "$BATCH_MARKER" "$CURRENT")"
CLEANED="$(remove_marker "$REFRESH_MARKER" "$CLEANED")"

{
    if [ -n "$CLEANED" ]; then printf "%s\n" "$CLEANED"; fi
    echo "$BATCH_CMD"
    echo "$REFRESH_CMD"
} | crontab -

echo "cron 설치 완료!"
echo ""
echo "등록된 작업:"
current_crontab | grep "naver-cafe-monitor"
echo ""
echo "로그 확인:"
echo "  tail -f $BATCH_LOG"
echo "  tail -f $REFRESH_LOG"
echo "제거: bash $0 --uninstall[=refresh|batch|all]"
