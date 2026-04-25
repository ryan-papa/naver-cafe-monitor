# Specify — Google Admin Login

## 1. 존재 이유

Naver Cafe Monitor 관리자 화면은 기존 이메일/비밀번호 로그인을 사용했다. 운영자는 museum-finder와 동일하게 Google 계정 기반 진입을 원하며, 로그인되지 않았거나 API 권한이 없을 때도 동일한 Google 로그인 흐름으로 보내야 한다.

## 2. 사용자

- 관리자: `/admin/posts`에서 카페 처리 이력을 확인하고 필요 시 상세/재발송을 수행한다.
- 운영자: 허용된 Google 계정만 관리자 세션을 받을 수 있어야 한다.

## 3. 핵심 장면

- 미인증 사용자가 `/admin` 또는 `/admin/posts`에 접근하면 `/login`으로 이동한다.
- `/login`은 인증 상태를 확인하고 미인증 또는 권한 없음이면 `/oauth2/authorization/google`로 이동한다.
- Google 로그인 성공 후 항상 `/admin/posts`로 이동한다.
- 기존 세션은 있으나 관리자 권한이 없으면 다시 Google 로그인으로 유도한다.

## 4. 경계

- 포함: FastAPI Google OAuth 시작/콜백, 관리자 API 권한 가드, 로그인 UI 자동 리다이렉트, 테스트.
- 제외: 실제 운영 reverse proxy 파일 수정, Google Cloud 콘솔 설정 자동화, 기존 이메일/비밀번호 API 삭제.

## 5. 성공 기준

- Google OAuth 콜백이 허용 이메일 계정에만 관리자 세션 쿠키를 발급한다.
- `/api/posts*`는 `is_admin=true` 사용자만 접근 가능하다.
- 로그인 성공 후 리다이렉트 목적지는 `/admin/posts`로 고정된다.
- 서버/프런트 빌드와 로그인 E2E가 통과한다.
