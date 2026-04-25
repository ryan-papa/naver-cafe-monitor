# T-DOCKER-BG (NCM) — QA 결과

| 게이트 | 상태 | 비고 |
|------|:--:|------|
| compose syntax | ✓ | `docker compose config --quiet` 통과 (mem_limit·healthcheck·user 10001·hardening 반영) |
| compose build (api+web) | ✓ | 둘 다 multi-stage 성공 |
| 배포 스크립트 syntax | ✓ | `bash -n` 통과 |
| pytest (api+shared) | ✓ | **93/93 passed** (ncm-api-green 컨테이너 안에서 pytest 설치 후 실행, 1.58s) |
| Playwright E2E | △ | 9/10 (1 fail은 main 에서 동일하게 실패하는 pre-existing 회귀, docker 변경 무관) |
| web 단독 smoke | ✓ | docker run + curl `/` → HTTP 302 `/admin` 정상 라우팅, 0 errors/warnings |
| api 단독 smoke | 배포 시 자동 | 실 MySQL + sops 의존, `scripts/deploy/docker_bluegreen_deploy.sh` `/api/health` + MySQL 에러 grep 게이트 |

## §10.1 MUST-FIX 14건 적용 현황

| # | 항목 | 상태 |
|:-:|------|:--:|
| 1 | `MYSQL_SSL_CERT_DIR_HOST:?required` | ✓ |
| 2 | mem_limit (api/web 384m) | ✓ |
| 3 | healthcheck + service_healthy | ✓ |
| 4 | docker/sops/openssl/python3/lsof 가드 | ✓ |
| 5 | .dockerignore 키파일 차단 | ✓ |
| 6 | api `/api/health` + MySQL 에러 grep 게이트 | ✓ |
| 7 | web `npm prune --omit=dev` | ✓ |
| 8 | INFRA_REPO_DIR 필수 (default 제거) | ✓ |
| 9 | workflow_dispatch actor allow-list | ✓ |
| 10 | restart on-failure:3 | ✓ |
| 11 | api non-root user 10001 | ✓ |
| 12 | 포트 :8000,4321 점유 가드 (lsof) | ✓ |
| 13 | non-root + no-new-privileges + cap_drop ALL | ✓ |
| 14 | `.pk8` chmod 600 | N/A (NCM compose_with_sops_env.py 는 .pk8 변환 무관) |

## 알려진 실패

**E2E `redirects.spec.ts` 1건** — `GET / unauthenticated → /oauth2/authorization/google` 매칭 기대인데 실제로는 redirect 가 accounts.google.com 까지 따라가서 매칭 실패. main 브랜치에서도 동일 실패 (`6760c3f Update login redirect E2E expectation` 이후 회귀 추정). docker 전환과 무관, 본 PR 영역 외.

## 비-스코프

| 항목 | 처리 |
|------|------|
| api smoke runtime | 배포 시 자동 (실 MySQL 의존) |
| 메모리 게이트 30분 | 배포 후 운영 측정 |
| 5xx=0 5분 게이트 | 배포 후 운영 측정 |
| OAuth redirect E2E 회귀 | 별도 PR (docker 전환 외 회귀) |
