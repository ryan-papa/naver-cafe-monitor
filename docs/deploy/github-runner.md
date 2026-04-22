# GitHub Runner Setup

Mac Mini 배포는 SSH 대신 GitHub Actions self-hosted runner로 수행한다.

## 표준 구조

- 러너: Mac Mini 1대에 공용 runner 1개 설치
- 라벨: `self-hosted`, `macOS`, `deploy`
- 저장소별 차이: `DEPLOY_REPO_DIR` 변수와 `scripts/deploy/mac_mini_deploy.sh`

## 1. GitHub 인증

`gh auth login -h github.com`

토큰이 만료된 경우 먼저 재로그인한다.

## 2. Runner 설치

```bash
GH_OWNER=<github-owner> \
GH_REPO=<repo-name> \
RUNNER_ROOT="$HOME/ActionsRunner" \
RUNNER_DIR_NAME="mac-mini-deploy" \
RUNNER_NAME="mac-mini-deploy" \
RUNNER_LABELS="macOS,deploy" \
bash scripts/deploy/install_github_runner.sh
```

설치 후 GitHub 저장소의 Actions runners 목록에 runner가 보여야 한다.

## 3. 저장소 변수 설정

```bash
GH_OWNER=<github-owner> \
GH_REPO=<repo-name> \
DEPLOY_REPO_DIR="/absolute/path/to/naver-cafe-monitor" \
bash scripts/deploy/configure_github_repo.sh
```

## 4. 배포 동작

- `main` push
- `Deploy` workflow 실행
- runner가 로컬 서버에서 `scripts/deploy/mac_mini_deploy.sh` 실행

## 다른 프로젝트 추가

다음 항목만 프로젝트별로 준비하면 된다.

- `.github/workflows/deploy.yml`
- `scripts/deploy/mac_mini_deploy.sh`
- GitHub variable `DEPLOY_REPO_DIR`

같은 Mac Mini runner를 그대로 재사용한다.
