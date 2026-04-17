# Task List: Auth (회원가입·로그인)

**PRD:** `docs/prd/20260417_202717_auth-signup-login_ad69d7f7.md`
**통합 브랜치:** `feat/auth-signup-login`

## 태스크

| ID | 설명 | PRD | 의존성 | 상태 | 브랜치 |
|----|------|-----|--------|------|--------|
| TA-01 | 시크릿 생성 + `.env.enc` 반영 (RSA-2048 keypair, AES-256 key, HMAC key, JWT secret) | F-03, F-11 | — | Done (주입 완료) | `feat/TA-01-secrets` |
| TA-02 | DB 마이그레이션: `users`, `refresh_tokens`, `auth_events`, `rate_limit_buckets` | F-01, F-07, F-14, F-15, F-06 | — | Done (적용 완료) | `feat/TA-02-schema` |
| TA-03 | 공통 암호화 유틸 (AES-GCM, HMAC-SHA256, argon2id, RSA-OAEP) | F-02, F-03, F-11 | TA-01 | Done | `feat/TA-03-crypto-utils` |
| TA-04 | JWT 발급·검증 유틸 (access 1h / refresh 24h) + 쿠키 헬퍼 | F-05, F-07 | TA-01 | Done | `feat/TA-04-jwt` |
| TA-05 | Rate limit 미들웨어 (IP + 계정, DB 버킷) | F-06 | TA-02 | Done | `feat/TA-05-ratelimit` |
| TA-06 | CSRF double-submit 미들웨어 | F-05, 비기능 | TA-04 | Done | `feat/TA-06-csrf` |
| TA-07 | `auth_events` 기록 유틸 | F-15 | TA-02 | Done | `feat/TA-07-events` |
| TA-08 | `/api/auth/public-key` 엔드포인트 | F-11 | TA-01, TA-03 | Done | `feat/TA-08-pubkey` |
| TA-09 | `/api/auth/signup` + `/api/auth/signup/confirm` (TOTP 발급·검증·활성화·자동로그인) | F-01~F-04, F-13 | TA-02~TA-07 | Done | `feat/TA-09-signup` |
| TA-10 | `/api/auth/login` (비번+TOTP, 실패 시 rate limit·lock) | F-05, F-06 | TA-02~TA-07 | Done | `feat/TA-10-login` |
| TA-11 | `/api/auth/refresh` (rotation + reuse detection + 단일 세션) | F-07, F-08 | TA-04, TA-07 | Done | `feat/TA-11-refresh` |
| TA-12 | `/api/auth/logout` + `/api/auth/me` + user_repository + current_user dependency | F-09 | TA-04 | Done | `feat/TA-12-logout-me` |
| TA-13 | 기존 `/api/posts/*` 보호: 인증 의존성 주입 | F-10 | TA-04 | Done | `feat/TA-13-protect-posts` |
| TA-14 | 초기 관리자 시드 스크립트 (`scripts/seed_admin.py`, env 1회 주입) | F-13 | TA-02, TA-03 | Done (admin user id=1 생성) | `feat/TA-14-seed-admin` |
| TA-15 | Astro SSR 전환 (`@astrojs/node`) + 미들웨어 가드 | F-10 | — | Done | `feat/TA-15-astro-ssr` |
| TA-16 | 프런트 로그인 페이지 (E2E: pubkey fetch → RSA-OAEP 암호화) | F-05, F-11 | TA-15, TA-08, TA-10 | Done | `feat/TA-16-login-ui` |
| TA-17 | 프런트 회원가입 3단계 페이지 (정보 → TOTP QR/백업코드 → 완료) | F-01, F-04, F-11 | TA-15, TA-08, TA-09 | Done | `feat/TA-17-signup-ui` |
| TA-18 | 프런트 공통 인증 컨텍스트 + 자동 refresh 인터셉터 | F-05, F-07 | TA-15, TA-11 | Done (TA-16 와 병합: `lib/auth-client.ts` csrfFetch) | `feat/TA-16-login-ui` |
| TA-19 | 에러 페이지 5종 (401/403/404/500/offline) + 공통 디자인 | F-12 | TA-15 | Done | `feat/TA-19-error-pages` |
| TA-20 | nginx 설정: `/api/auth/*` 통과, 루트는 Astro SSR(Node) 프록시 | F-10 | TA-15 | Todo | `feat/TA-20-nginx` |
| TA-21 | Unit 테스트 (crypto, argon2, TOTP, rate limit, JWT) | 테스트 | TA-03~TA-07 | Todo | `feat/TA-21-unit` |
| TA-22 | Integration 테스트 (signup→TOTP→login→rotation→logout 풀 플로우) | 테스트 | TA-09~TA-12 | Todo | `feat/TA-22-integration` |
| TA-23 | Security 테스트 (reuse detection, CSRF, lockout, 잠금 해제) | 테스트 | TA-05, TA-06, TA-11 | Todo | `feat/TA-23-security` |
| TA-24 | E2E 테스트 Playwright (가입·로그인·에러페이지) | 테스트 | TA-16, TA-17, TA-19 | Todo | `feat/TA-24-e2e` |
| TA-25 | 운영 문서 (README, 키 rotation 절차, TOTP 분실 복구) | 비기능 | — | Todo | `feat/TA-25-docs` |

## 의존성 그래프 (요약)

```
TA-01 (secrets) ──┬─► TA-03 (crypto) ──┐
                  │                     ├─► TA-08 (pubkey)
                  └─► TA-04 (jwt) ──────┤
                                        ├─► TA-09 (signup)
TA-02 (schema) ──┬─► TA-05 (ratelimit) ─┤
                 ├─► TA-07 (events) ────┤
                 │                      ├─► TA-10 (login)
                 └─► TA-14 (seed)       │
                                        ├─► TA-11 (refresh)
TA-04 ──► TA-06 (csrf) ─────────────────┤
                                        └─► TA-12 (logout/me)
                                              │
TA-13 (protect-posts) ◄───────────────────────┘

TA-15 (astro-ssr) ──┬─► TA-16 (login-ui)
                    ├─► TA-17 (signup-ui)
                    ├─► TA-18 (auth-context)
                    ├─► TA-19 (error-pages)
                    └─► TA-20 (nginx)

TA-21..TA-24 (tests) ─ 해당 구현 이후
TA-25 (docs) ─ 병렬 가능, 배포 전 필수
```

## 진행 순서

1. **Phase 1 — 기반** (TA-01, TA-02, TA-03, TA-04)
2. **Phase 2 — 미들웨어** (TA-05, TA-06, TA-07)
3. **Phase 3 — API** (TA-08, TA-09, TA-10, TA-11, TA-12, TA-13, TA-14)
4. **Phase 4 — 프런트** (TA-15, TA-16, TA-17, TA-18, TA-19)
5. **Phase 5 — 인프라** (TA-20)
6. **Phase 6 — 테스트·문서** (TA-21~TA-25)
