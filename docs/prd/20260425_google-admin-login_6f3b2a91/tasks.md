# Tasks — Google Admin Login

- 통합 브랜치: `main`
- 태스크 브랜치: `feat/google-admin-login`

## T-01 Backend OAuth

- `/oauth2/authorization/google` 추가
- `/login/oauth2/code/google` 추가
- state 검증, token 교환, userinfo 조회
- whitelist 기반 관리자 세션 발급

## T-02 Admin Gate

- `current_admin` dependency 추가
- `/api/posts*` 보호 API를 admin gate로 변경
- 기존 허용 이메일 사용자의 admin 승격 지원

## T-03 Frontend Redirect

- `/login`을 Google OAuth 진입점으로 변경
- `/admin*` SSR에서 401/403/non-admin 상태를 `/login`으로 redirect
- OAuth 성공 후 `/admin/posts`로 고정 redirect

## T-04 Verification

- API 단위 테스트 추가/수정
- 로그인 E2E 수정
- 빌드 검증
