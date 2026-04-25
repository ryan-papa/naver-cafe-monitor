#!/usr/bin/env bash
set -euo pipefail

DEPLOY_REPO_DIR="${DEPLOY_REPO_DIR:-}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
INFRA_REPO_DIR="${INFRA_REPO_DIR:-}"
COMPOSE_FILE="deploy/compose.bluegreen.yaml"
INFRA_SWITCH_ENABLED="${INFRA_SWITCH_ENABLED:-0}"

if [[ -z "$DEPLOY_REPO_DIR" ]]; then
  echo "DEPLOY_REPO_DIR is required." >&2
  exit 1
fi
if [[ -z "$INFRA_REPO_DIR" ]]; then
  echo "INFRA_REPO_DIR is required." >&2
  exit 1
fi

ACTIVE_FILE="${INFRA_REPO_DIR}/state/naver-cafe-monitor.active"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

# Entry guards
for cmd in docker sops openssl python3 lsof; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "required command not found: $cmd" >&2
    exit 1
  fi
done
if ! docker info >/dev/null 2>&1; then
  echo "docker daemon is not reachable. start Docker Desktop and retry." >&2
  exit 1
fi

cd "$DEPLOY_REPO_DIR"

if [[ -n "$(git status --short)" ]]; then
  echo "Working tree is not clean. Refusing to deploy over local changes." >&2
  git status --short
  exit 1
fi

git fetch origin "$DEPLOY_BRANCH"
if [[ "$(git branch --show-current)" != "$DEPLOY_BRANCH" ]]; then
  git checkout "$DEPLOY_BRANCH"
fi
git pull --ff-only origin "$DEPLOY_BRANCH"

active="blue"
[[ -f "$ACTIVE_FILE" ]] && active="$(tr -d '[:space:]' < "$ACTIVE_FILE")"
if [[ "$INFRA_SWITCH_ENABLED" != "1" ]]; then
  # Compatibility mode: green only on legacy ports (8000/4321).
  # Active state file intentionally not updated — host nginx still owns routing.
  target="green"
  old=""
  api_port="${NCM_API_GREEN_PORT:-8000}"
  web_port="${NCM_WEB_GREEN_PORT:-4321}"
  export NCM_API_GREEN_PORT="$api_port"
  export NCM_WEB_GREEN_PORT="$web_port"
elif [[ "$active" == "blue" ]]; then
  target="green"
  old="blue"
  api_port="${NCM_API_GREEN_PORT:-18001}"
  web_port="${NCM_WEB_GREEN_PORT:-14322}"
else
  target="blue"
  old="green"
  api_port="${NCM_API_BLUE_PORT:-18000}"
  web_port="${NCM_WEB_BLUE_PORT:-14321}"
fi

# Port occupancy guard - prevent collision with uvicorn / Node entry processes
for port in "$api_port" "$web_port"; do
  occupant="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | awk 'NR>1 {print $1"/"$2}' | head -1 || true)"
  if [[ -n "$occupant" ]]; then
    if ! docker ps --format '{{.Names}} {{.Ports}}' | grep -q ":$port->"; then
      echo "port $port is held by non-docker process ($occupant). stop uvicorn / Node entry before deploying." >&2
      exit 1
    fi
  fi
done

run_compose() {
  python3 scripts/deploy/compose_with_sops_env.py --env-file .env.enc \
    docker compose -f "$COMPOSE_FILE" "$@"
}

run_compose up -d --build "ncm-api-${target}" "ncm-web-${target}"

# Resolve api container id for log inspection
api_cid="$(python3 scripts/deploy/compose_with_sops_env.py --env-file .env.enc \
  docker compose -f "$COMPOSE_FILE" ps -q "ncm-api-${target}" | head -1)"
if [[ -z "$api_cid" ]]; then
  echo "Failed to resolve container id for ncm-api-${target}." >&2
  exit 1
fi

for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:${api_port}/api/health" >/dev/null; then
    break
  fi
  sleep 2
done

if ! curl -fsS "http://127.0.0.1:${api_port}/api/health" >/dev/null; then
  echo "New ${target} API did not become healthy on port ${api_port}." >&2
  docker logs "$api_cid" 2>&1 | tail -30 >&2 || true
  run_compose stop "ncm-api-${target}" "ncm-web-${target}" || true
  exit 1
fi

# MySQL connection error guard
if docker logs "$api_cid" 2>&1 | grep -iE "mysql.*(error|denied|refused|timeout)" >/dev/null; then
  echo "MySQL connection error detected in ncm-api-${target} logs." >&2
  docker logs "$api_cid" 2>&1 | grep -iE "mysql" | tail -10 >&2 || true
  run_compose stop "ncm-api-${target}" "ncm-web-${target}" || true
  exit 1
fi

for _ in {1..30}; do
  if curl -fsSI "http://127.0.0.1:${web_port}/" >/dev/null; then
    break
  fi
  sleep 2
done

if ! curl -fsSI "http://127.0.0.1:${web_port}/" >/dev/null; then
  echo "New ${target} web did not become healthy on port ${web_port}." >&2
  run_compose stop "ncm-api-${target}" "ncm-web-${target}" || true
  exit 1
fi

if [[ "$INFRA_SWITCH_ENABLED" == "1" ]]; then
  "${INFRA_REPO_DIR}/scripts/switch-upstream.sh" ncm "$target"
  run_compose stop "ncm-web-${old}" "ncm-api-${old}" || true
fi

echo "naver-cafe-monitor deployed to ${target}."
