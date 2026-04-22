#!/bin/bash
set -euo pipefail

GH_OWNER="${GH_OWNER:-}"
GH_REPO="${GH_REPO:-}"
DEPLOY_REPO_DIR="${DEPLOY_REPO_DIR:-}"
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-production}"

if [[ -z "${GH_OWNER}" || -z "${GH_REPO}" || -z "${DEPLOY_REPO_DIR}" ]]; then
  echo "GH_OWNER, GH_REPO, and DEPLOY_REPO_DIR are required." >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required." >&2
  exit 1
fi

gh variable set DEPLOY_REPO_DIR \
  --repo "${GH_OWNER}/${GH_REPO}" \
  --body "${DEPLOY_REPO_DIR}"

gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  "repos/${GH_OWNER}/${GH_REPO}/environments/${ENVIRONMENT_NAME}"

echo "Configured ${GH_OWNER}/${GH_REPO}"
