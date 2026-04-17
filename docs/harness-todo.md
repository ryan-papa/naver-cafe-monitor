# Harness · Security TODO

회고 (`rp-retro`) 2026-04-17 에서 도출된 항목. 우선순위 숫자가 높을수록 빠르게.

## 미반영 개선 (회고 번호 4·5·6·7·8·10)

| # | 항목 | 우선순위 | 비고 |
|:-:|------|:-------:|------|
| 4 | nginx 보안 헤더 기본 추가 (CSP / HSTS / X-Frame-Options / X-Content-Type-Options / Referrer-Policy / Permissions-Policy) | High | 외부(`ncm.eepp.store`) 공개 전 필수 |
| 5 | DB 마이그레이션 도구 alembic 도입 + 롤백 스크립트 규칙 | Mid | 향후 스키마 변경 복잡해질 때 시급도↑ |
| 6 | `rate_limit_buckets` cleanup cron 등록 + `auth_events` 경고 알림 (카카오톡 채널 재사용) | Mid | 외부 오픈 시 고려 |
| 7 | 에러 응답 스키마 표준화 `{code, message}` 또는 RFC7807 problem+json | Low | 프런트에서 매핑 중 — 일단 동작은 OK |
| 8 | 키 rotation 자동화 스크립트 (`scripts/auth/rotate_*.py`) + cron | Mid | 유출 대응 시 유용 |
| 10 | structured logging (JSON) + request_id propagation | Low | 관측성 개선 |

## 배포 이중화 — Phase A (프로세스 이중화)

단일 맥미니에서 배포 무중단 rolling deploy. 장비 장애까지 방어는 안 함 (Phase B 별도).

| 과제 | 내용 |
|------|------|
| 프로세스 매니저 | launchd plist 4개 (uvicorn×2, astro-ssr×2) — 자동 재시작·부팅 시 기동 |
| 포트 할당 | uvicorn 8000/8001, astro-ssr 4321/4322 |
| nginx upstream | `upstream api { server 127.0.0.1:8000; server 127.0.0.1:8001; }` + `upstream web { ... }` |
| 헬스체크 | nginx OSS passive only → FastAPI `/api/health` + Astro `/health` 추가 |
| Rolling 스크립트 | `scripts/deploy/rolling.sh` — 한 쪽 drain(nginx upstream 제거 or backup 플래그) → 재시작 → 통과 대기 → 반대편 |
| 로그 | `/opt/homebrew/var/log/ncm/{api,web}-{0,1}.log` |
| 설정 재적용 | sops 복호화 후 env 주입 wrapper 재사용 (현 `generate_secrets.py` 패턴) |

**Phase B (장비·리전 이중화)** — 별도 과제로 두고, 트래픽·수익 발생 후 재검토:
- Cloudflare DNS 이관 (health check + failover)
- Oracle Cloud ARM free tier 혹은 fly.io 에 app 노드 추가
- MySQL 매니지드 이전 (PlanetScale / Neon / AWS RDS) 또는 read replica
- age recipients 에 새 노드 키 추가 후 sops 재암호화
- ISP 회선 다중화 (또는 클라우드 노드만으로 외부 오픈 구성)

## 반영된 항목 (본 회고 즉시 적용)

| # | 내용 | 위치 |
|:-:|------|------|
| 1 | TOTP QR 을 클라이언트 사이드 렌더링(`qrcode` npm)으로 교체 — 외부 서비스로 secret 전송 차단 | `web/src/lib/qr.ts`, signup/2fa 페이지 |
| 2 | `rp-qa` + `rp-code-review` 생략 방지 게이트 강화 | `CLAUDE.md` 절대규칙, `rp-ship.md` 절대규칙 |
| 3 | feat/통합 브랜치 직행 배포 금지 | `CLAUDE.md`, `rp-ship.md` |
| 9 | 프런트 Playwright E2E + axe 접근성 검사 필수 | `rp-qa.md` 기능 QA / 디자인 QA |
