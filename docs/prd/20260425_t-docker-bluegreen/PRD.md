# T-DOCKER-BG — Docker Compose 블루-그린 배포 전환 (NCM)

> **상태**: Full PRD (역추출, museum-finder T-DOCKER-BG 동형)
> **통합 브랜치**: `main`
> **feat 브랜치**: `feat/t-docker-bluegreen`

## 1. 배경 (Why)

| 항목 | 내용 |
|------|------|
| 현재 | uvicorn `api.src.main:app` (127.0.0.1:8000) + Astro Node entry (`web/dist/server/entry.mjs` 4321) + nginx reverse proxy. 배포 시 `kill` + 재실행 |
| 문제 | (1) 인플레이스 코드 갱신 → 동일 디렉터리에서 빌드+재기동 회귀 위험 (museum-finder 와 동일). (2) 배포 파이프라인이 launchd 스타일 직접 빌드라 다른 레포(museum-finder) 와 분기 → 운영 부담 |
| 변경 | Docker Compose 기반 컨테이너 2 셋(blue·green) + 별도 `deploy-infra` 레포의 nginx upstream 스위칭으로 무중단 배포. museum-finder 와 동일 deploy-infra 인프라 공유 |
| 사용자 가치 | 무중단 배포로 (a) 크롤링 누락 0 (배포 중 cron 실행 영향 차단), (b) 카페 게시글 알림 지연 0, (c) 외부 콜백(OAuth) 단절 0 |
| 의존 | museum-finder T-DOCKER-BG (#68) 과 deploy-infra 레포 머지 완료 |

## 2. 범위 (What / What Not)

### 포함
- `api/Dockerfile` (FastAPI uvicorn) + `web/Dockerfile` (Astro Node)
- `deploy/compose.bluegreen.yaml` (ncm-{api,web}-{blue,green} 4 서비스, host MySQL·SSL cert 마운트)
- 배포 스크립트 `scripts/deploy/docker_bluegreen_deploy.sh` + sops env helper `compose_with_sops_env.py`
- `.dockerignore`
- `.github/workflows/deploy.yml` 변경 (mac_mini_deploy → docker_bluegreen_deploy)
- `docs/docker-bluegreen.md` 운영 가이드
- `api/src/main.py` `/api/health` endpoint 추가
- `shared/database.py` MySQL 호스트·포트·user·db 환경변수화 (`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_DATABASE`, `MYSQL_SSL_CERT_DIR`)
- 프로젝트 `CLAUDE.md` 갱신 (uvicorn 직접 실행 → Compose blue/green)

### 미포함
- nginx 설정·upstream 스위칭 (`switch-upstream.sh`) → `deploy-infra` 레포 (이미 머지됨)
- batch (cron) 컨테이너화 — 별도 PR (현행 cron 유지)
- launchd plist unload (운영자 수동)

## 2.1. 대안 탐색

museum-finder PRD §2.1 동일 결론. Docker Compose 채택. 본 PRD 에서는 NCM 고유 제약 추가 검토:

| 제약 | 영향 | 채택안 처리 |
|------|------|------------|
| MySQL SSL cert 호스트 디렉터리 공유 (mf 와 동일 경로 가능성) | 두 레포 동시에 ro 마운트 시 충돌 없음(read-only) | `MYSQL_SSL_CERT_DIR_HOST` GH Variable 로 분리 주입, default 제거 |
| cron 배치 (30분 주기) | 컨테이너화 시 cron 호스트 의존 변화 | 본 사이클 미포함, 호스트 cron 유지 (별도 PR) |
| Mac Mini 8GB 공유 (mf+ncm) | 동시 배포 시 RSS ≥5.0GB | `concurrency: museum-eepp-shared` GH Actions 그룹 또는 deploy-infra 단일 락 (§5 #7 보강) |
| Astro Node prod runtime | 단일 진입 (`entry.mjs`) — multi-stage 효과 작음 | image 크기보다 RSS 최적화 우선, `npm prune --omit=dev` 유지 |

**채택 근거**: 엔지니어 선호(mf 와 통일) + 운영 가설(동일 deploy-infra 재사용으로 운영비 절감)

## 3. 아키텍처

```
사용자 → nginx (deploy-infra, 443)
         ├─ active=blue  → api :18000 / web :14321
         └─ active=green → api :18001 / web :14322

호환 모드 (INFRA_SWITCH_ENABLED=0, 기본):
         green 만 :8000 / :4321 점유 (기존 nginx upstream 호환)
```

| 컨테이너 | 포트 | 비고 |
|---------|------|------|
| `ncm-api-blue` | 127.0.0.1:18000 | FastAPI uvicorn |
| `ncm-web-blue` | 127.0.0.1:14321 | Astro Node entry |
| `ncm-api-green` | 127.0.0.1:18001 (전환) / 8000 (호환) | |
| `ncm-web-green` | 127.0.0.1:14322 (전환) / 4321 (호환) | |

**메모리 limit**

| 컨테이너 | mem_limit | 근거 |
|---------|:---------:|------|
| ncm-api-* | 384m | uvicorn + python 메모리 평균 ~250MB |
| ncm-web-* | 384m | Astro Node prod runtime ~250MB |

**RSS 추산** (Mac Mini 8GB, museum-finder 와 동일 호스트 공유)

| 시나리오 | api | web | 합계 (museum-finder 정상 2.6GB 포함) |
|---------|:--:|:--:|:--:|
| 정상(active 만) | 1×384 | 1×384 | ~3.4GB |
| 전환 중 (blue+green) | 2×384 | 2×384 | ~4.2GB |
| 위험 (mf+ncm 동시 배포) | 2×384 | 2×384 | ≥5.0GB △ |

MySQL SSL cert: 호스트 디렉터리 ro 마운트 → `/run/secrets/mysql-client/`

## 4. 시크릿 처리

- `.env.enc` (sops+age) 만 커밋
- `compose_with_sops_env.py` 가 메모리 복호화 → docker compose env 주입 (평문 디스크 미생성)
- 필수: `MYSQL_PASSWORD`, `AUTH_AES_KEY`, `AUTH_HMAC_KEY`, `AUTH_JWT_SECRET`
- 옵션: `AUTH_RSA_*`, `GOOGLE_*`, `KAKAO_*`, `LOG_LEVEL`

## 5. 배포 플로우

museum-finder 와 동일. 단, MySQL 사용 (PG·Flyway 무관). 헬스체크 endpoint = `/api/health` (api), `/` (web).

| 단계 | 동작 |
|:--:|------|
| 1 | GitHub Actions self-hosted runner (`main` push 트리거) |
| 2 | `git pull --ff-only` |
| 3 | active color 결정 (`deploy-infra/state/naver-cafe-monitor.active`) |
| 4 | inactive color 빌드+up |
| 5 | api `/api/health` (30회×2초) + web `/` (30회×2초) 헬스체크 |
| 6 | `INFRA_SWITCH_ENABLED=1` 시 `deploy-infra/scripts/switch-upstream.sh ncm <target>` 호출 후 old color stop |

## 6. 마이그레이션 단계

| 순서 | 액션 | 검증 |
|:--:|------|------|
| 1 | 본 PR main 머지 (호환 모드) | green 컨테이너 :8000/:4321, 기존 nginx 호환 |
| 2 | uvicorn / Node entry 프로세스 stop (운영자 수동) | `pkill -f "uvicorn api.src.main"` 등 |
| 3 | deploy-infra nginx 활성화 (이미 머지됨) | nginx :443 owner |
| 4 | GH Variable `INFRA_SWITCH_ENABLED=1` (운영자 수동 + dry-run + 사용자 승인) | blue↔green 자동 스위칭 |

롤백: `INFRA_SWITCH_ENABLED=0` + uvicorn / Node entry 재시작.

## 7. 테스트·검증

| 게이트 | 내용 |
|------|------|
| 빌드 | `docker compose build ncm-api-green ncm-web-green` 성공 |
| smoke | green 컨테이너 기동 후 `/api/health` 200 + `/` 200 |
| MySQL 연결 | api 부팅 로그에 connection 에러 없음, `/api/health` 응답 < 1s |
| 시크릿 | `compose_with_sops_env.py` 단독 — sops 복호화 → env 출력 정상 |
| 보안 | `docker exec` 로 `/app/.env` 부재 확인 |
| 단위 | `pytest` 통과 |
| Playwright E2E (web) | 기존 스위트 통과 |
| 무중단 트래픽 | nginx access log 5분 5xx=0 |
| 메모리 | `docker stats` api ≤ 350MB · web ≤ 350MB 30분 |
| 전환 모드 dry-run | INFRA_SWITCH_ENABLED=1 첫 배포 직전 1회 + 사용자 승인 |

## 8. 리스크

| # | 리스크 | 완화 |
|:-:|------|------|
| 1 | Mac Mini 메모리 (mf 와 공유) | mem_limit + 동시 배포 직렬화. `.github/workflows/deploy.yml` 에 `concurrency: museum-eepp-shared-host` (mf 와 동일 그룹명) 으로 동시 실행 차단. `docker stats` 모니터링 |
| 2 | host MySQL·sops 의존 | 배포 스크립트 진입 가드 (docker info / sops / openssl / python3 / lsof) |
| 3 | SSL cert 호스트 경로 default (`${HOME}/.ssl/client-certs`) | CLAUDE.md ⛔ 민감 정보 위반 → `${MYSQL_SSL_CERT_DIR_HOST:?required}` 강제 |
| 4 | 호환 모드 ↔ 전환 모드 단방향 | 동일. 회귀 시 uvicorn / Node entry 재시작 |
| 5 | docker daemon down | `docker info` 가드 + abort + 운영자 수동 fallback |
| 6 | git status 가드 untracked 차단 | .dockerignore ↔ .gitignore 정합 점검 |
| 7 | 호환 모드 :8000/:4321 점유 (uvicorn / Node entry 살아있을 때) | `lsof -nP -iTCP:8000,4321 -sTCP:LISTEN` 가드 |
| 8 | 헬스체크 실패 시 부분 기동 컨테이너 | green stop cleanup + blue 보존 |
| 9 | mTLS / OAuth 흐름 | 컨테이너 환경에서 `GOOGLE_OAUTH_REDIRECT_URI` 등 변경 없음 검증 |
| 10 | INFRA_SWITCH_ENABLED 전환 게이트 | 운영자 수동 + dry-run 승인 |

## 9. 성공 기준

- [ ] CI 통과 + 호환 모드 1회 무중단 배포 (사용자 영향 0)
- [ ] `docker stats` api ≤ 350MB / web ≤ 350MB 30분
- [ ] CLAUDE.md uvicorn → Compose blue/green 갱신
- [ ] compose 절대경로 default 제거
- [ ] `/api/health` endpoint 200

## 10. 영향 파일

| 종류 | 경로 |
|------|------|
| 신규 | `api/Dockerfile`, `.dockerignore`, `deploy/compose.bluegreen.yaml`, `scripts/deploy/docker_bluegreen_deploy.sh`, `scripts/deploy/compose_with_sops_env.py`, `docs/docker-bluegreen.md` |
| 수정 | `web/Dockerfile`, `.github/workflows/deploy.yml`, `api/src/main.py` (/api/health), `shared/database.py` (env 화), `CLAUDE.md` |
| 삭제 | (없음, uvicorn / Node entry 정리는 별도) |

## 10.1. Pre-merge MUST-FIX (museum-finder 동형 13건 + NCM 보강 1건)

| # | 등급 | 항목 | 파일 | 상세 |
|:-:|:--:|------|------|------|
| 1 | Critical | SSL cert dir host default 제거 | `deploy/compose.bluegreen.yaml` | `${MYSQL_SSL_CERT_DIR_HOST:?required}` |
| 2 | High | mem_limit 명시 | compose 4 services | api/web 각 384m + mem_reservation |
| 3 | High | healthcheck + depends_on service_healthy | compose | api `/api/health`, web `/` |
| 4 | High | 배포 스크립트 진입 가드 | deploy script | docker info / sops / openssl / python3 / lsof |
| 5 | High | .dockerignore 키파일 차단 | `.dockerignore` | `**/*.pem`, `**/*.pk8`, `**/*.key`, `**/.ssh`, `**/id_rsa*` |
| 6 | High | api 부팅 검증 게이트 | 배포 스크립트 | `/api/health` 200 + 응답 < 1s, MySQL connection error 부재 grep |
| 7 | Medium | Astro Node entry 이미지 최적화 | `web/Dockerfile` | `node_modules` prune 또는 `--omit=dev` |
| 8 | Medium | INFRA_REPO_DIR default 제거 | 배포 스크립트 | default 절대경로 삭제. GH Variable 강제 |
| 9 | Medium | workflow_dispatch actor 게이트 | `.github/workflows/deploy.yml` | `DEPLOY_TRIGGER_ACTORS` allow-list |
| 10 | Medium | OOM 무한 재시작 방지 | compose | `restart: on-failure:3` |
| 11 | Medium | api Dockerfile exec PID 1 + non-root | `api/Dockerfile` | `CMD ["uvicorn",...]` 는 이미 exec 형. non-root user 10001 추가 |
| 12 | High | 호환 모드 포트 :8000/:4321 점유 가드 | 배포 스크립트 | `lsof -nP -iTCP:8000,4321 -sTCP:LISTEN` |
| 13 | High | 컨테이너 런타임 하드닝 | compose 4 services | `user: "10001:10001"`, `no-new-privileges:true`, `cap_drop:[ALL]` |
| 14 | High | `.pk8` 권한 (museum-finder 회고) | `compose_with_sops_env.py` | NCM 은 .pk8 변환 불요 (MySQL SSL 직접). 그러나 동일 wrapper 사용 시 chmod 600 유지 — museum-finder fix 그대로 적용 |
