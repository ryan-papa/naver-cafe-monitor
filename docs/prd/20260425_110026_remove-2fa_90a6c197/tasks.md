# Tasks: 2차 인증(TOTP) 완전 제거

**PRD:** `prd.md`
**브랜치:** `feat/remove-2fa`
**통합 브랜치:** `main`

---

## 진행 순서

| # | 태스크 | 영역 | 상태 | 의존성 |
|---|--------|------|------|--------|
| T-01 | DB 마이그레이션 작성 (DROP + DOWN 페어) | DB | TODO | — |
| T-02 | `shared/auth_tokens.py` 의 `totp_setup_required` 필드·디코드 처리 제거 | Shared | TODO | — |
| T-03 | `shared/auth_events.py` totp 이벤트 enum 제거 | Shared | TODO | — |
| T-04 | `shared/user_repository.py` TOTP 컬럼 R/W 제거 | Shared | TODO | T-01 |
| T-05 | `shared/host_classifier.py` + 동반 테스트 삭제 | Shared | TODO | T-06,T-07 |
| T-06 | `api/src/auth/login_service.py` TOTP·LoginContext.internal 제거 + `__all__`/docstring 동기화 | API | TODO | T-02,T-03 |
| T-07 | `api/src/auth/router.py` `is_internal` 호출·totp_code 파라미터 제거 | API | TODO | T-06 |
| T-08 | `api/src/auth/signup_service.py` TOTP 시크릿 생성·저장 제거 | API | TODO | T-04 |
| T-09 | `api/src/auth/token_service.py` `totp_setup_required` 클레임 제거 (F-15 호환성: 디코드 시 무시) | API | TODO | T-02 |
| T-10 | `api/src/auth/dependencies.py` setup_required 게이트 + `SETUP_ALLOWED_PREFIXES`/`_is_setup_allowed_path` 제거 | API | TODO | T-09 |
| T-11 | `api/src/auth/settings_2fa.py` 파일 삭제 | API | TODO | — |
| T-12 | `api/src/main.py` `settings_2fa_router` include 제거 | API | TODO | T-11 |
| T-13 | `api/pyproject.toml` + `api/requirements.txt` 의 `pyotp` 의존성 제거 | API | TODO | T-06 |
| T-14 | `web/src/pages/login.astro` TOTP 입력 필드·로직 제거 | Web | TODO | T-07 |
| T-15 | `web/src/pages/signup.astro` TOTP 단계 제거 | Web | TODO | T-08 |
| T-16 | `web/src/pages/admin/settings/2fa.astro` + `web/src/pages/settings/2fa.astro` 파일 삭제 | Web | TODO | T-11 |
| T-17 | `web/src/components/admin/Sidebar.astro` 2FA 메뉴 제거 | Web | TODO | — |
| T-18 | `web/src/middleware.ts` `totp_setup_required` 분기 제거 | Web | TODO | T-09 |
| T-19 | API 단위 테스트 정리: test_auth_login, test_settings_2fa, test_setup_required_guard, test_login_domain_branch, test_auth_signup, test_auth_me_logout, test_api | API tests | TODO | T-06~T-12 |
| T-20 | F-15 호환성 단위 테스트 추가: 기존 토큰의 `totp_setup_required` 클레임 무시 검증 | API tests | TODO | T-09 |
| T-21 | `shared/tests/test_user_repository.py` TOTP 케이스 제거 | Shared tests | TODO | T-04 |
| T-22 | E2E 테스트 정리: `web/tests/e2e/login.spec.ts`, `web/tests/e2e/redirects.spec.ts` | E2E | TODO | T-14~T-18 |
| T-23 | `scripts/auth/seed_admin.py` + `scripts/auth/generate_secrets.py` TOTP 부분 제거 | Scripts | TODO | T-04 |
| T-24 | README · CLAUDE.md · `.env.example` 의 2FA 문구 정리 | Docs | TODO | — |
| T-25 | grep 게이트 검증: 소스 트리 0 hit | QA | TODO | T-01~T-24 |
| T-26 | 백엔드 테스트 4-게이트 통과 확인 (단위·GET API·DB 통합·bootRun) | QA | TODO | T-25 |
| T-27 | Playwright E2E + axe 통과 확인 | QA | TODO | T-25 |

---

## 비고

- 마이그레이션은 raw SQL (`db/migrations/20260425_drop_totp_columns.sql` + `..._down.sql`)
- `auth_events.event_type` 컬럼 타입을 사전 확인하여 enum 이면 별도 마이그레이션 추가 (T-03 내부)
- `host_classifier` 삭제 전 router/login_service 의 import 가 모두 정리되어야 함 (T-06, T-07 선행)
- F-15 의 토큰 호환성: 디코드 시 `totp_setup_required` 키 무시. 기존 토큰의 만료까지 자연 정리
