#!/bin/bash
set -euo pipefail

DEPLOY_REPO_DIR="${DEPLOY_REPO_DIR:-}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
API_PATTERN="${API_PATTERN:-uvicorn api.src.main}"
WEB_PATTERN="${WEB_PATTERN:-web/dist/server/entry.mjs}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-4321}"
API_LOG_PATH="${API_LOG_PATH:-/tmp/uvicorn.log}"
WEB_LOG_PATH="${WEB_LOG_PATH:-/tmp/astro.log}"

kill_listener() {
  local port="$1"

  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN || true)"
    if [[ -n "${pids}" ]]; then
      kill ${pids}
      return 0
    fi
  fi

  return 1
}

if [[ -z "${DEPLOY_REPO_DIR}" ]]; then
  echo "DEPLOY_REPO_DIR is required." >&2
  exit 1
fi

if [[ ! -d "${DEPLOY_REPO_DIR}/.git" ]]; then
  echo "DEPLOY_REPO_DIR must point to a git repository: ${DEPLOY_REPO_DIR}" >&2
  exit 1
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH}"

cd "${DEPLOY_REPO_DIR}"

if [[ -n "$(git status --short)" ]]; then
  echo "Working tree is not clean. Refusing to deploy over local changes." >&2
  git status --short
  exit 1
fi

if ! pgrep -f "${API_PATTERN}" >/dev/null; then
  echo "API process is not running. Refusing to deploy on an uninitialized server." >&2
  exit 1
fi

git fetch origin "${DEPLOY_BRANCH}"

current_branch="$(git branch --show-current)"
if [[ "${current_branch}" != "${DEPLOY_BRANCH}" ]]; then
  git checkout "${DEPLOY_BRANCH}"
fi

git pull --ff-only origin "${DEPLOY_BRANCH}"

pushd web >/dev/null
npm ci
npm run build
popd >/dev/null

kill_listener "${API_PORT}" || pkill -f "${API_PATTERN}" || true
nohup "${DEPLOY_REPO_DIR}/deploy/scripts/run-api.sh" > "${API_LOG_PATH}" 2>&1 &
sleep 2

if ! pgrep -f "${API_PATTERN}" >/dev/null; then
  echo "API failed to restart. See ${API_LOG_PATH}" >&2
  exit 1
fi

kill_listener "${WEB_PORT}" || pkill -f "${WEB_PATTERN}" || true
nohup node "${DEPLOY_REPO_DIR}/web/dist/server/entry.mjs" > "${WEB_LOG_PATH}" 2>&1 &
sleep 2

if ! pgrep -f "${WEB_PATTERN}" >/dev/null; then
  echo "Web failed to restart. See ${WEB_LOG_PATH}" >&2
  exit 1
fi

echo "Deployment completed successfully."
