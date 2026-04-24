#!/usr/bin/env bash
# install_cron.sh 테스트 — crontab 스텁 기반
#
# 시나리오:
#   1. 설치 → 2개 엔트리 등록
#   2. 재실행 → 멱등 (각 마커 1줄씩 유지)
#   3. --uninstall=refresh → refresh만 제거
#   4. --uninstall=batch → batch 제거
#   5. --uninstall=all → 전체 제거
#   6. --uninstall=foo → exit 2
#   7. 재설치 → 정상 복구

set -euo pipefail

THIS_DIR="$(cd "$(dirname "$0")" && pwd)"
BATCH_DIR="$(cd "$THIS_DIR/.." && pwd)"
INSTALL_SCRIPT="$BATCH_DIR/scripts/install_cron.sh"

# 임시 HOME / crontab 스텁
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT

CRON_FILE="$TMP_ROOT/crontab.txt"
touch "$CRON_FILE"

STUB_BIN="$TMP_ROOT/bin"
mkdir -p "$STUB_BIN"
cat > "$STUB_BIN/crontab" <<EOF
#!/usr/bin/env bash
if [ "\${1:-}" = "-l" ]; then
    cat "$CRON_FILE" 2>/dev/null || true
elif [ "\${1:-}" = "-" ]; then
    cat > "$CRON_FILE"
else
    echo "stub crontab: unsupported args: \$*" >&2
    exit 1
fi
EOF
chmod +x "$STUB_BIN/crontab"

export PATH="$STUB_BIN:$PATH"

# venv 스텁 (install_cron.sh 가 존재 확인만 함)
VENV_STUB="$TMP_ROOT/venv"
mkdir -p "$VENV_STUB/bin"
touch "$VENV_STUB/bin/python"
chmod +x "$VENV_STUB/bin/python"
export VENV_DIR="$VENV_STUB"

fail() { echo "FAIL: $*" >&2; exit 1; }

count_marker() {
    grep -c -F "$1" "$CRON_FILE" 2>/dev/null || true
}

# ── 1. 최초 설치 ──────────────────────────────────────────────────────────
bash "$INSTALL_SCRIPT" >/dev/null
b1=$(count_marker "# naver-cafe-monitor batch")
r1=$(count_marker "# naver-cafe-monitor kakao-refresh")
[ "$b1" = "1" ] || fail "최초 설치 후 batch 마커=$b1 (expected 1)"
[ "$r1" = "1" ] || fail "최초 설치 후 refresh 마커=$r1 (expected 1)"

# ── 2. 재실행 멱등 ─────────────────────────────────────────────────────────
bash "$INSTALL_SCRIPT" >/dev/null
bash "$INSTALL_SCRIPT" >/dev/null
b2=$(count_marker "# naver-cafe-monitor batch")
r2=$(count_marker "# naver-cafe-monitor kakao-refresh")
[ "$b2" = "1" ] || fail "3회 실행 후 batch 마커=$b2 (expected 1, 멱등성 위반)"
[ "$r2" = "1" ] || fail "3회 실행 후 refresh 마커=$r2 (expected 1, 멱등성 위반)"

# ── 3. --uninstall=refresh ─────────────────────────────────────────────────
bash "$INSTALL_SCRIPT" --uninstall=refresh >/dev/null
b3=$(count_marker "# naver-cafe-monitor batch")
r3=$(count_marker "# naver-cafe-monitor kakao-refresh")
[ "$b3" = "1" ] || fail "--uninstall=refresh 후 batch=$b3 (expected 1)"
[ "$r3" = "0" ] || fail "--uninstall=refresh 후 refresh=$r3 (expected 0)"

# ── 4. --uninstall=batch ───────────────────────────────────────────────────
bash "$INSTALL_SCRIPT" >/dev/null
bash "$INSTALL_SCRIPT" --uninstall=batch >/dev/null
b4=$(count_marker "# naver-cafe-monitor batch")
r4=$(count_marker "# naver-cafe-monitor kakao-refresh")
[ "$b4" = "0" ] || fail "--uninstall=batch 후 batch=$b4 (expected 0)"
[ "$r4" = "1" ] || fail "--uninstall=batch 후 refresh=$r4 (expected 1)"

# ── 5. --uninstall=all ─────────────────────────────────────────────────────
bash "$INSTALL_SCRIPT" >/dev/null
bash "$INSTALL_SCRIPT" --uninstall=all >/dev/null
b5=$(count_marker "# naver-cafe-monitor batch")
r5=$(count_marker "# naver-cafe-monitor kakao-refresh")
[ "$b5" = "0" ] || fail "--uninstall=all 후 batch=$b5 (expected 0)"
[ "$r5" = "0" ] || fail "--uninstall=all 후 refresh=$r5 (expected 0)"

# 기본값 --uninstall (인자 없음) = all
bash "$INSTALL_SCRIPT" >/dev/null
bash "$INSTALL_SCRIPT" --uninstall >/dev/null
b5b=$(count_marker "# naver-cafe-monitor batch")
r5b=$(count_marker "# naver-cafe-monitor kakao-refresh")
[ "$b5b" = "0" ] && [ "$r5b" = "0" ] || fail "--uninstall(no value) 기본값 all 실패"

# ── 6. --uninstall=foo → exit 2 ────────────────────────────────────────────
set +e
bash "$INSTALL_SCRIPT" --uninstall=foo >/dev/null 2>&1
rc=$?
set -e
[ "$rc" = "2" ] || fail "--uninstall=foo exit code=$rc (expected 2)"

# ── 7. 재설치 복구 ─────────────────────────────────────────────────────────
bash "$INSTALL_SCRIPT" >/dev/null
b7=$(count_marker "# naver-cafe-monitor batch")
r7=$(count_marker "# naver-cafe-monitor kakao-refresh")
[ "$b7" = "1" ] && [ "$r7" = "1" ] || fail "재설치 복구 실패 batch=$b7 refresh=$r7"

echo "PASS: install_cron.sh 7 시나리오"
