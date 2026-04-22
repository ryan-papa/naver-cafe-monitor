#!/bin/bash
set -euo pipefail

RUNNER_ROOT="${RUNNER_ROOT:-$HOME/ActionsRunner}"
RUNNER_VERSION="${RUNNER_VERSION:-2.329.0}"
RUNNER_ARCHIVE="actions-runner-osx-arm64-${RUNNER_VERSION}.tar.gz"
RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_ARCHIVE}"
RUNNER_DIR_NAME="${RUNNER_DIR_NAME:-mac-mini-deploy}"
RUNNER_DIR="${RUNNER_ROOT}/${RUNNER_DIR_NAME}"
GH_OWNER="${GH_OWNER:-}"
GH_REPO="${GH_REPO:-}"
RUNNER_NAME="${RUNNER_NAME:-macos-deploy-runner}"
RUNNER_LABELS="${RUNNER_LABELS:-macOS,deploy}"

if [[ -z "${GH_OWNER}" || -z "${GH_REPO}" ]]; then
  echo "GH_OWNER and GH_REPO are required." >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required." >&2
  exit 1
fi

mkdir -p "${RUNNER_ROOT}"

if [[ ! -d "${RUNNER_DIR}" ]]; then
  mkdir -p "${RUNNER_DIR}"
  pushd "${RUNNER_DIR}" >/dev/null
  curl -L -o "${RUNNER_ARCHIVE}" "${RUNNER_URL}"
  tar xzf "${RUNNER_ARCHIVE}"
  rm -f "${RUNNER_ARCHIVE}"
  popd >/dev/null
fi

registration_token="$(
  gh api \
    --method POST \
    "repos/${GH_OWNER}/${GH_REPO}/actions/runners/registration-token" \
    --jq '.token'
)"

pushd "${RUNNER_DIR}" >/dev/null

if [[ ! -f .runner ]]; then
  ./config.sh \
    --unattended \
    --url "https://github.com/${GH_OWNER}/${GH_REPO}" \
    --token "${registration_token}" \
    --name "${RUNNER_NAME}" \
    --labels "${RUNNER_LABELS}" \
    --work "_work"
fi

./svc.sh install
./svc.sh start

popd >/dev/null

echo "Runner installed at ${RUNNER_DIR}"
