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

## 반영된 항목 (본 회고 즉시 적용)

| # | 내용 | 위치 |
|:-:|------|------|
| 1 | TOTP QR 을 클라이언트 사이드 렌더링(`qrcode` npm)으로 교체 — 외부 서비스로 secret 전송 차단 | `web/src/lib/qr.ts`, signup/2fa 페이지 |
| 2 | `rp-qa` + `rp-code-review` 생략 방지 게이트 강화 | `CLAUDE.md` 절대규칙, `rp-ship.md` 절대규칙 |
| 3 | feat/통합 브랜치 직행 배포 금지 | `CLAUDE.md`, `rp-ship.md` |
| 9 | 프런트 Playwright E2E + axe 접근성 검사 필수 | `rp-qa.md` 기능 QA / 디자인 QA |
