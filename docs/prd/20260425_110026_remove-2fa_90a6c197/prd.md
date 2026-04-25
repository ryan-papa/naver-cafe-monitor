# PRD: 2차 인증(TOTP) 완전 제거

**ID:** 20260425_110026_remove-2fa_90a6c197
**날짜:** 2026-04-25
**상태:** Draft

---

## 문제·맥락

- **배경:** 운영 환경(`ncm.eepp.shop`)이 외부 노출에서 mTLS 차단으로 전환 예정. 외부 접근이 막히면 2FA 보호의 실효 효용이 소멸한다. 동시에, 현재 nginx Host 헤더 미전달로 인해 내부 도메인에서도 2FA 면제 분기가 동작하지 않아 운영자가 매 로그인마다 TOTP 입력으로 마찰을 겪는다.
- **원인:** `request.url.hostname` 이 업스트림 주소(`127.0.0.1`)로 잡혀 `host_classifier.is_internal()` 가 항상 `False` 를 반환 → `LoginContext.internal=False` → TOTP 검증 강제. 상세는 직전 분석 참조.
- **왜 지금:** 외부 차단 결정과 동시에 보호 효용이 0 인 코드 경로를 유지할 이유가 사라짐. 인증/암호화 자산(AES, RSA, argon2, CSRF, rate-limit, mTLS) 은 그대로 둔다.

## 타깃 사용자와 사용 맥락

| 항목 | 내용 |
|------|------|
| 대상 사용자 | 단일 운영자 (관리자 계정 1개) |
| 사용 맥락 | 사내망 + mTLS 클라이언트 인증서 보유 PC 에서 `https://ncm.eepp.shop/admin` 진입 |
| 핵심 동기 | 빠른 로그인, 인증 마찰 제거 |

## 핵심 시나리오

| # | 장면 | 사용자 행동 | 시스템 반응 |
|---|------|-----------|-----------|
| 1 | 로그인 | 이메일·비밀번호 입력 후 제출 | 검증 후 즉시 `/admin` 진입. TOTP 입력 칸 없음 |
| 2 | 신규 계정 시드 | `seed_admin` CLI 로 관리자 생성 | TOTP 시크릿 발급 없이 생성 완료 |
| 3 | 기존 데이터 마이그레이션 | 배포 시 마이그레이션 자동 실행 | `users.totp_enabled`, `users.totp_secret_enc` 컬럼 DROP |

**실패 모드 테이블:**

| 코드경로 | 시나리오 | 감지 방법 (테스트) | UX 대응 |
|----------|----------|------------------|---------|
| `/api/auth/login` | 잘못된 비번 | 단위 테스트 (test_auth_login) | 401 `invalid_credentials` |
| `/api/auth/login` | rate limit 초과 | 단위 테스트 | 429 |
| 마이그레이션 | 컬럼 미존재 (idempotent) | `IF EXISTS` 사용 | 성공 |
| 프런트 `/login` | TOTP 입력 필드 노출 여부 | Playwright E2E | 필드 자체 비표시 |
| `/admin/settings/2fa` | 페이지 접근 | E2E 404 또는 redirect 검증 | 라우트 제거 |

## 대안 탐색 (A/B/C/D)

| 대안 | 요약 | 장점 | 단점 | 공수 | 판단 근거 유형 |
|------|------|------|------|------|--------------|
| A | 로그인 시 TOTP 검증만 우회 | 최소 변경, 롤백 쉬움 | 사용 안 하는 코드/UI/DB 잔존 | XS | 엔지니어 선호 |
| B | 검증 + 설정 UI 제거, DB 컬럼·서비스 유지 | 중간 절충 | 절반 작업, 코드 정합성 깨짐 | S | — |
| **C (선택)** | 검증·UI·라우터·서비스·DB 컬럼·마이그레이션·테스트·`pyotp`·`host_classifier`·`LoginContext.internal` 일괄 제거 | 코드 단순화, 유지보수 면적 축소, 보안 면적 축소 | 롤백 시 전부 복원 필요 | M | 제품 가설 (외부 차단 결정 확정) |
| D (현상 유지) | 비활성화 안 함 | 변경 없음 | 사용자 마찰 지속, dead code 누적 | — | — |

**선택:** C
**선택 근거:** 외부 차단 결정으로 2FA 의 보호 효용이 0 이 됨. dead code 누적은 보안 audit 시 노이즈 증가. 호스트 분류 분기 자체가 무용해지므로 함께 제거.

## 톤·정체성 (Voice)

| 항목 | 정의 |
|------|------|
| 톤 | 변경 없음 (관리자 전용 UI) |
| 어투 | 변경 없음 |
| 금칙어 | — |
| 레퍼런스 | — |
| 삭제 대상 문구 | `2단계 인증`, `TOTP`, `Authenticator`, `OTP 코드`, `2FA` |

## 스코프 & 비-스코프

| 포함 (In) | 비포함 (Out) |
|-----------|-------------|
| `LoginContext.internal`, `is_internal` 호출부 제거 | mTLS 설정 |
| `verify_totp`, TOTP 분기 로직 제거 | argon2/RSA/AES/CSRF/rate-limit 로직 |
| `api/src/auth/settings_2fa.py` 라우터·테스트 제거 | 세션·refresh 토큰 전략 |
| `web/src/pages/admin/settings/2fa.astro`, `web/src/pages/settings/2fa.astro` 제거 | 로그인 폼 디자인 변경 |
| `login.astro` TOTP 입력 필드·로직 제거 | `users` 테이블 외 다른 테이블 |
| `signup.astro` TOTP 안내·로직 제거 (있다면) | 백업/복호화 정책 |
| Sidebar 의 2FA 메뉴 항목 제거 | 알림(카카오) 채널 |
| middleware 의 `totp_setup_required` 분기 제거 | |
| `users.totp_enabled`, `users.totp_secret_enc` DROP 마이그레이션 | |
| `signup_service`, `user_repository` 의 TOTP 컬럼 처리 제거 | |
| `auth_events` 의 `totp_ok`/`totp_fail` 이벤트 타입 제거 | |
| `pyotp` 의존성 제거 (`api/pyproject.toml`) | |
| `shared/host_classifier.py` 파일 삭제 | |
| `seed_admin.py`, `generate_secrets.py` 의 TOTP 부분 제거 | |
| 모든 관련 단위·E2E 테스트 정리 (제거 또는 갱신) | |

## 성공 기준 & 실패 기준

| 구분 | 지표 | 목표값 |
|------|------|--------|
| 성공 | 로그인 성공률 | 100% (TOTP 미입력 상태) |
| 성공 | 코드 grep `totp\|TOTP\|pyotp\|2fa\|two_factor` | **소스 트리 한정** (`api/`, `shared/`, `web/src/`, `db/`, `scripts/`, `*.toml`, `*.txt`) 0 hit. **예외**: F-15 호환성 테스트(`shared/tests/test_token_legacy_claim.py`), legacy enum 보존 docstring(`shared/auth_events.py`), 신규 마이그레이션 본문(`db/migrations/20260425_*`), 라우트 제거 검증 E2E(`web/tests/e2e/*.spec.ts`) 의도된 잔존. `web/dist/`, `node_modules/`, `__pycache__`, `.pytest_cache` 제외 |
| 성공 | 단위 테스트 통과 | 100% |
| 성공 | F-15 호환성 단위 테스트 | 과거 발급 토큰의 `totp_setup_required` 클레임이 검증·미들웨어에서 무시됨을 확인 |
| 성공 | E2E (Playwright) 로그인 시나리오 | 통과 |
| 성공 | axe 접근성 검사 | 로그인·관리자 페이지 전부 violation 0 (하네스 규칙) |
| 성공 | 마이그레이션 idempotent 적용 | 재실행 시 오류 없음 |
| 실패 | 로그인 실패 | 즉시 롤백 |
| 실패 | DB 컬럼 DROP 실패 | 마이그레이션 롤백 |

## 가정 · 리스크 · 열린 질문

| 유형 | 내용 | 검증 방법 |
|------|------|----------|
| 가정 | 운영 환경에서 외부 노출이 차단된다 (mTLS only) | 운영자 확인 완료 |
| 가정 | 단일 관리자 계정만 존재 | DB 조회 불필요, 코드 기준 그대로 |
| 리스크 | 외부 차단 정책이 향후 변경될 경우 보호 공백 | 그 시점에 별도 인증 강화 PRD 재발행 |
| 리스크 | DB 컬럼 DROP 후 복구 비용 | 마이그레이션 down 스크립트 보존 |
| 리스크 | 테스트 파일 다수 삭제로 회귀 커버리지 감소 | 로그인·세션·CSRF 핵심 테스트는 유지 |
| 열린 질문 | `auth_events` 테이블의 기존 `totp_ok`/`totp_fail` 레코드 | 보존 (감사 기록), 신규 발행만 중단 |

---

## 기능 요구사항

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| F-01 | 로그인 API 는 이메일·비밀번호만 검증, TOTP 코드 입력 자체를 받지 않는다 | Must |
| F-02 | `/admin/settings/2fa`, `/settings/2fa` 라우트 및 페이지 파일 제거 | Must |
| F-03 | 로그인 폼에서 TOTP 입력 UI 제거 | Must |
| F-04 | Sidebar 의 "2단계 인증" 메뉴 제거 | Must |
| F-05 | 회원가입(signup) 흐름에서 TOTP 관련 단계·안내·필드 제거 | Must |
| F-06 | `users.totp_enabled`, `users.totp_secret_enc`, `users.backup_codes_hash` 컬럼 DROP 마이그레이션 추가 (`backup_codes_hash` 는 TOTP 부속 컬럼이므로 동시 정리) | Must |
| F-07 | `pyotp` 의존성 제거 | Must |
| F-08 | `shared/host_classifier.py` 파일 삭제 + 모든 호출부 제거 | Must |
| F-09 | `LoginContext.internal` 필드 제거 | Must |
| F-10 | `auth_events` 이벤트 enum 에서 `totp_ok`, `totp_fail`, `totp_setup_*` 제거 (신규 발행 차단) | Must |
| F-11 | 토큰 페이로드에서 `totp_setup_required` 클레임 제거, `setup_required` 게이트 미들웨어 분기 제거 | Must |
| F-12 | 관련 단위·E2E·통합 테스트 정리 (제거 또는 갱신) | Must |
| F-13 | `seed_admin.py`, `generate_secrets.py` 의 TOTP 부분 제거 | Should |
| F-14 | README · CLAUDE.md · `.env.example` 의 2FA 관련 문구 정리 (grep 0 hit 게이트와 직결) | Must |
| F-15 | 기존 발급된 access/refresh 토큰의 `totp_setup_required` 클레임은 검증·미들웨어 모두 무시 (호환성). 토큰 만료 시 자연 정리 | Must |
| F-16 | 운영자 수동 합격 체크리스트: ① mTLS PC 에서 `/admin` 진입 ② 이메일·비번만 입력 후 로그인 성공 ③ `/admin/settings/2fa` 접근 시 404 ④ Sidebar 에 2FA 메뉴 비표시 | Must |

## 비기능 요구사항

| 항목 | 요구사항 |
|------|----------|
| 성능 | 로그인 latency 변화 ≤ ±5% (TOTP 검증 제거로 미세 단축 예상) |
| 보안 | argon2·RSA·AES·CSRF·rate-limit·mTLS·refresh 토큰 회전 그대로 유지. 외부 차단은 nginx 측에서 보장 |
| 확장성 | 향후 mTLS 외 추가 인증 도입 시 PRD 재발행. 현 변경은 전제 변경에 따른 단순화 |

## 기술 스택 · 제약사항

| 항목 | 내용 |
|------|------|
| 기술 스택 | FastAPI, Astro SSR, PostgreSQL, pytest, Playwright, axe |
| 기술 제약 | 마이그레이션은 raw SQL (기존 `db/migrations/*.sql` 패턴 유지) |
| 비즈니스 제약 | 운영자 1인 계정. 단일 환경 (Mac mini). 외부 차단은 nginx mTLS 로 보장 |

## 변경 영향 파일 (요약)

| 영역 | 파일 | 작업 |
|------|------|------|
| API | `api/src/auth/login_service.py` | TOTP 분기·`verify_totp`·`LoginContext.internal` 제거 |
| API | `api/src/auth/router.py` | `is_internal` import·호출 제거, totp_code 파라미터 제거 |
| API | `api/src/auth/settings_2fa.py` | 파일 삭제 |
| API | `api/src/auth/signup_service.py` | TOTP 시크릿 생성·저장 제거 |
| API | `api/src/auth/token_service.py` | `totp_setup_required` 클레임 제거 |
| API | `api/src/auth/dependencies.py` | setup_required 게이트 제거 |
| API | `api/src/main.py` | `settings_2fa_router` include 제거 |
| API | `api/pyproject.toml` | `pyotp` 의존성 제거 |
| Shared | `shared/host_classifier.py` | 파일 삭제 |
| Shared | `shared/tests/test_host_classifier.py` | 파일 삭제 (동반 제거) |
| Shared | `shared/auth_events.py` | totp 이벤트 enum 제거 |
| Shared | `shared/user_repository.py` | TOTP 컬럼 R/W 제거 |
| Shared | `shared/auth_tokens.py` | `totp_setup_required` 필드·디코드 처리 제거 (F-11·F-15 핵심 구현 지점) |
| Shared | `shared/crypto.py` | TOTP 전용 보조 함수가 있을 경우만 제거 (AES 일반 유지) |
| API | `api/requirements.txt` | `pyotp` 항목 제거 (`pyproject.toml` 과 동시) |
| API | `api/src/auth/dependencies.py` | `SETUP_ALLOWED_PREFIXES`·`_is_setup_allowed_path` 부속 헬퍼까지 제거 |
| API | `api/src/auth/login_service.py` | `verify_totp`·`LoginContext.internal` 제거 + `__all__`·docstring 동기화 |
| Web | `web/src/pages/login.astro` | TOTP 입력 필드·로직 제거 |
| Web | `web/src/pages/signup.astro` | TOTP 단계 제거 |
| Web | `web/src/pages/admin/settings/2fa.astro` | 파일 삭제 |
| Web | `web/src/pages/settings/2fa.astro` | 파일 삭제 |
| Web | `web/src/components/admin/Sidebar.astro` | 2FA 메뉴 제거 |
| Web | `web/src/middleware.ts` | `totp_setup_required` 분기 제거 |
| Web | `web/tests/e2e/login.spec.ts` | TOTP 단계 제거 또는 케이스 삭제 |
| Web | `web/tests/e2e/redirects.spec.ts` | 2FA 리다이렉트 케이스 제거 |
| DB | `db/migrations/<new>.sql` | `ALTER TABLE users DROP COLUMN IF EXISTS totp_enabled, totp_secret_enc` |
| Tests | `api/tests/test_auth_login.py`, `test_settings_2fa.py`, `test_setup_required_guard.py`, `test_login_domain_branch.py`, `test_auth_signup.py`, `test_auth_me_logout.py`, `test_api.py`, `shared/tests/test_user_repository.py` | TOTP·internal 케이스 제거, 핵심 케이스만 유지 |
| Scripts | `scripts/auth/seed_admin.py`, `scripts/auth/generate_secrets.py` | TOTP 부분 제거 |
| Docs | `README.md`, `CLAUDE.md`, `.env.example` | 2FA 문구 정리 |

## 롤백 계획

| 단계 | 절차 |
|------|------|
| 1 | `git revert` 로 머지 커밋 되돌림 |
| 2 | 마이그레이션 down 적용 — `db/migrations/20260425_drop_totp_columns_down.sql` 실행. **데이터 손실**: 컬럼만 복원되고 기존 `totp_secret_enc`, `backup_codes_hash` 데이터는 모두 NULL/false 로 초기화됨 (DROP 시점에 데이터 영구 소실) |
| 3 | 운영자에게 신규 TOTP 시크릿 재발급 + 백업 코드 재생성 후 등록 |

---

## Review 결과

### 기획 리뷰 (Planning Review)

| 회차 | 명확성 | 완성도 | 실현가능성 | 일관성 | 측정가능성 | 경계 명확성 | 분기 충분성 | 사용자 검증 게이트 | 대안 탐색 | 평균 |
|------|--------|--------|-----------|--------|-----------|-----------|-----------|-------------------|----------|------|

**판정:** \_\_\_ / 10
**피드백:** -

### 엔지니어링 리뷰 (Engineering Review)

| 회차 | 요구사항 명확성 | 기술적 실현가능성 | 범위·공수 | NFR | 의존성·리스크 | 테스트 가능성 | 평균 |
|------|---------------|-----------------|----------|-----|-------------|-------------|------|

**판정:** \_\_\_ / 10
**피드백:** -

### 최종 판정

\_\_\_ → `Approved` / `Max retry reached`
