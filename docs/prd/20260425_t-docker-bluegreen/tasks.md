# T-DOCKER-BG (NCM) — Tasks

| 항목 | 값 |
|------|----|
| 통합 브랜치 | `main` |
| feat 브랜치 | `feat/t-docker-bluegreen` (생성됨, 코덱스 변경분 적재) |

## Tasks

| ID | 설명 | 상태 |
|:--:|------|:--:|
| T-01 | feat 브랜치 (이미 main 에서 분기 완료) | Done |
| T-02 | compose.bluegreen.yaml MUST-FIX: SSL default 제거(#1)·mem_limit(#2)·healthcheck(#3)·on-failure:3(#10)·hardening(#13)·user 10001(#11)·**concurrency 그룹 통일은 deploy.yml 에서** | Todo |
| T-03 | docker_bluegreen_deploy.sh: 진입 가드(#4)·INFRA_REPO_DIR 필수(#8)·포트 :8000,4321 점유 가드(#12) | Todo |
| T-04 | .dockerignore 키파일 차단(#5) | Todo |
| T-05 | api/Dockerfile: non-root 10001·wget(헬스체크용) | Todo |
| T-06 | web/Dockerfile: non-root 10001·wget·`npm prune --omit=dev`(#7) | Todo |
| T-07 | .github/workflows/deploy.yml: actor allow-list(#9) + `concurrency: museum-eepp-shared-host` (mf 와 통일) | Todo |
| T-08 | compose_with_sops_env.py: museum-finder 의 chmod 600 패턴 — NCM 은 .pk8 변환 무관하나 동일 wrapper 시 기능 유지 (museum-finder 카피 시 자동 포함) | Todo |
| T-09 | 프로젝트 CLAUDE.md: uvicorn 직접 실행 → Compose blue/green 운영 정책 갱신 | Todo |
| T-10 | smoke build: `docker compose build ncm-api-green ncm-web-green` | Todo |
| T-11 | smoke runtime: web 단독 부팅 + curl /. api 는 실 MySQL 의존이라 배포 시 자동 검증 | Todo |
| T-12 | unit 테스트: pytest (api), 기존 테스트 통과 | Todo |
| T-13 | E2E: web Playwright (있으면) | Todo |

## 의존

T-01 → T-02..T-08 → T-09 → T-10 → T-11 → T-12·T-13

## 비-스코프 (별도 PR / 운영자 수동)

- uvicorn / Node entry process stop (PRD §6 #2, 운영자 수동)
- batch cron 컨테이너화 (별도 PR)
- INFRA_SWITCH_ENABLED=1 활성화 (운영자 수동 + dry-run + 사용자 승인)
