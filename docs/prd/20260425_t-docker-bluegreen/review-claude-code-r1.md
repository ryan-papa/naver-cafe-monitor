# Code Review (Claude) — r1

| 항목 | 점수 | 근거 |
|------|:--:|------|
| 정확성 | 9 | MUST-FIX 14건 전수 반영. `/api/health` `{"status":"ok"}` ↔ healthcheck grep 정확 매칭 |
| 설계·구조 | 9 | YAML anchor·단일 책임·이중 경로(호환/전환) 명확 |
| 가독성 | 8 | 배포 스크립트 주석. parse_dotenv 인라인 코멘트 부족 |
| 테스트 품질 | 8 | pytest 93/93·smoke·compose syntax. E2E pre-existing 격리 |
| 보안 | 9 | dockerignore·SSL default 제거·non-root·cap_drop·no-new-privileges·sops·actor 게이트·:127.0.0.1 |
| 성능·효율 | 8 | mem_limit·prune·on-failure:3·healthcheck start_period |
| 유지보수성 | 9 | INFRA_SWITCH 플래그·concurrency 통일·CLAUDE.md 동기화 |

**종합**: 평균 8.57 / 최저 8 / **통과**

## 잔여 (Medium·Low, ship 후 retro)

| # | 등급 | 항목 |
|:-:|:--:|------|
| 1 | Medium | parse_dotenv PEM 종결 토큰 일반화 (RSA/CERTIFICATE 등) |
| 2 | Medium | web Dockerfile prune 순서 — devDependencies 잔류 가능성 |
| 3 | Low | MySQL 에러 grep 헬스체크 이전 로그 false positive 가능 |
