> 이 문서는 프로젝트 로컬 규칙이며 최우선 적용된다.
> **⛔ 세션 시작 시 `../../CLAUDE.md`를 반드시 Read로 읽고 적용할 것.**
> 충돌 시 본 문서(프로젝트)가 우선한다.

# naver-cafe-monitor

## Deployment

| 항목 | 내용 |
|------|------|
| 서버 환경 | 로컬 Mac Mini (museum-finder 와 호스트 공유) |
| 배포 트리거 | GitHub Actions self-hosted runner (`self-hosted`, `macOS`, `deploy`) |
| 배포 모드 | Docker Compose 블루-그린 (T-DOCKER-BG 이후) |
| 통합 브랜치 | `main` (push 시 자동 배포) |
| 배치 | cron 30분 주기 (호스트 cron 유지, 컨테이너화 미포함) |
| 프록시 | nginx (deploy-infra 레포 소유) |
| 동시 배포 락 | GH Actions concurrency group `museum-eepp-shared-host` (museum-finder 와 통일 — 단, mf 는 별도 PR 로 그룹명 통일 필요) |

**컨테이너 정책**

| 항목 | 값 |
|------|----|
| mem_limit | api 384m / web 384m + mem_reservation 동일 |
| restart | `on-failure:3` |
| user | `10001:10001` (베이스 이미지 기존 user 충돌 회피) |
| 보안 | `cap_drop:[ALL]`, `no-new-privileges:true`, healthcheck 의무 |
| 시크릿 | `.env.enc` (sops+age) → `compose_with_sops_env.py` 메모리 복호화. 평문 디스크 미생성 |
| SSL cert | `MYSQL_SSL_CERT_DIR_HOST` GH Variable 강제 (compose default 금지) |

**모드**

| 모드 | 동작 | 포트 |
|------|------|------|
| 호환 (`INFRA_SWITCH_ENABLED=0`, 기본) | green 만 :8000/:4321 점유, 기존 nginx 호환 | api 8000, web 4321 |
| 전환 (`=1`, deploy-infra 머지 후) | blue↔green 자동 스위칭, deploy-infra `switch-upstream.sh ncm` 호출 | blue api 18000 / web 14321, green api 18001 / web 14322 |

**필수 GH Repository Variables**

| 변수 | 용도 |
|------|------|
| `DEPLOY_REPO_DIR` | self-hosted runner 의 ncm 레포 클론 경로 |
| `INFRA_REPO_DIR` | deploy-infra 클론 경로 |
| `MYSQL_SSL_CERT_DIR_HOST` | MySQL client SSL cert 호스트 디렉터리 |
| `DEPLOY_TRIGGER_ACTORS` | workflow_dispatch 허용 actor JSON 배열 (예: `["ryan-papa"]`) |

**호스트 도구**: Docker Desktop, sops, openssl, python3, lsof.

**배포 절차**:
1. `git pull --ff-only`
2. `scripts/deploy/docker_bluegreen_deploy.sh` (compose build → green up → `/api/health` 헬스체크 + MySQL 연결 에러 grep → web 헬스체크 → INFRA_SWITCH_ENABLED=1 시 deploy-infra `switch-upstream.sh ncm` → old color stop)

**배포 시 유의사항**

| # | 규칙 | 근거 |
|:-:|------|------|
| 1 | green 컨테이너 빌드는 격리된 BuildKit context 에서만 수행 | 인플레이스 덮어쓰기 회귀 차단 |
| 2 | 헬스체크 통과 후에만 nginx 스위칭 | 미통과 시 즉시 abort + green stop |
| 3 | 호환↔전환 단방향 | 부분 회귀 금지. 회귀 시 uvicorn / Node entry 재시작 + `INFRA_SWITCH_ENABLED=0` |
| 4 | 포트 점유 가드 | 진입부 `lsof -nP -iTCP:8000,4321 -sTCP:LISTEN` 로 uvicorn / Node entry 점유 시 abort |
| 5 | 메모리 게이트 | api/web 각 ≤ 350MB 30분 |
| 6 | MySQL 연결 검증 | api 부팅 로그 `(mysql.*(error\|denied\|refused\|timeout))` 매칭 시 abort |
| 7 | SSL cert 호스트 경로는 환경변수만 | compose default 절대경로 작성 금지 |
| 8 | 시크릿 평문 디스크 미생성 | `compose_with_sops_env.py` 가 `os.environ` 으로만 전달 |

**마이그레이션 단계** (T-DOCKER-BG 이후)

| 순서 | 액션 | 비고 |
|:--:|------|------|
| 1 | 본 PR main 머지 | green 컨테이너 :8000/:4321, 기존 nginx 호환 |
| 2 | uvicorn / Node entry 프로세스 stop | 운영자 수동 (`pkill -f "uvicorn api.src.main"` 등) |
| 3 | deploy-infra nginx 활성화 | 이미 머지됨 |
| 4 | `INFRA_SWITCH_ENABLED=1` 활성화 | 운영자 수동 + dry-run + 사용자 승인 |

**비-스코프 (별도 PR / 운영자 수동)**

- batch (cron) 컨테이너화 — 호스트 cron 유지 (별도 PR)
- museum-finder concurrency group 통일 (별도 PR — 현재 mf 는 `museum-finder-production`)
