# PRD — Google Admin Login

## 프로젝트 개요

Naver Cafe Monitor는 네이버 카페 게시글 수집·요약·카카오 발송 이력을 관리하는 내부 관리자 도구다. 이번 변경은 기존 이메일/비밀번호 관리자 로그인을 Google OAuth 기반 로그인으로 전환해 museum-finder와 동일한 운영 경험을 제공한다.

대상 사용자는 허용된 Google 계정을 가진 관리자다.

## 핵심 시나리오 + 실패 모드

| 코드 경로 | 시나리오 | 감지 | UX 대응 |
|---|---|---|---|
| `/login` | 인증 상태 확인 성공 + admin | `/api/auth/me` 200, `is_admin=true` | `/admin/posts`로 replace |
| `/login` | 미인증 | `/api/auth/me` 401 | `/oauth2/authorization/google`로 이동 |
| `/login` | API 권한 없음 | `/api/auth/me` 403 또는 `is_admin=false` | Google 로그인으로 이동 |
| `/oauth2/authorization/google` | OAuth 시작 | Google env 존재 | Google authorization URL로 302 |
| `/login/oauth2/code/google` | OAuth 성공 | state 일치, verified email | 세션 쿠키 발급 후 `/admin/posts` |
| OAuth 콜백 | 허용되지 않은 계정 | whitelist 불일치 | 403 `oauth_login_forbidden` |
| `/api/posts*` | 비관리자 접근 | `is_admin=false` | 403 |

## 대안 탐색

| 대안 | 설명 | 판단 |
|---|---|---|
| A | 기존 이메일/비밀번호 유지 | museum-finder와 운영 경험이 달라 요구 불충족 |
| B | 프런트에서만 Google 링크 제공 | API 권한 없음 처리와 서버 세션 발급이 불완전 |
| C | FastAPI에 OAuth 엔드포인트 추가 | 현재 구조와 쿠키 세션을 유지하면서 요구 충족 |
| D | 별도 인증 프록시 도입 | 범위가 과하고 배포 리스크 증가 |

선택: C. 기존 FastAPI JWT/refresh/csrf 쿠키 체계를 재사용하고, Google OAuth만 서버 진입점으로 추가한다.

## 톤·정체성

- 로그인 페이지는 기존 관리자 UI의 간결한 톤을 유지한다.
- 화면 문구는 기능 설명보다 상태와 행동만 짧게 전달한다.
- 금칙: 내부 구현 세부사항, OAuth 오류 상세, 시크릿 이름 노출.

## 기능 요구사항

- F-01: 서버는 `/oauth2/authorization/google`에서 Google OAuth를 시작한다. 우선순위 P0.
- F-02: 서버는 `/login/oauth2/code/google`에서 state 검증, 토큰 교환, userinfo 조회를 수행한다. 우선순위 P0.
- F-03: verified email이 아니거나 허용 이메일 목록에 없으면 세션을 발급하지 않는다. 우선순위 P0.
- F-04: 허용 이메일의 기존 사용자가 `is_admin=false`이면 관리자 권한으로 승격 후 세션을 발급한다. 우선순위 P1.
- F-05: OAuth 성공 후 항상 `/admin/posts`로 redirect한다. 우선순위 P0.
- F-06: `/api/posts`, `/api/posts/{id}`, `/api/posts/{id}/resend`는 관리자 권한을 요구한다. 우선순위 P0.
- F-07: `/login`은 미인증 또는 권한 없음 상태에서 Google OAuth로 자동 이동한다. 우선순위 P0.
- F-08: `/admin*` SSR 페이지는 API 인증/권한 실패를 `/login` redirect로 처리한다. 우선순위 P1.

## AI 기능 검증

해당 없음. LLM/AI 판단 기능이 추가되지 않는다.

## 기술 스택

- Backend: FastAPI, PyJWT, PyMySQL, urllib 표준 라이브러리
- Frontend: Astro SSR, Playwright, Vitest
- Auth: Google OAuth 2.0, 기존 access/refresh/csrf 쿠키

## 제약사항

- 운영 reverse proxy는 실제 서버에서 OAuth 시작/콜백 경로를 FastAPI로 보내야 한다.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_ADMIN_ALLOWED_EMAILS`가 서버 환경변수로 필요하다.
- 로컬 테스트는 Google 실 API 호출 대신 state/권한/리다이렉트 단위 검증으로 제한한다.

## 공개 전환 시나리오

OAuth client secret과 허용 이메일 목록은 환경변수로만 주입한다. PRD와 코드에는 실제 이메일/시크릿을 포함하지 않는다. 레포 공개 전환 시에도 Google Cloud OAuth client 설정 화면의 redirect URI와 시크릿은 별도 비밀 관리 대상이다.

## Open Issues

- 실제 운영 서버의 reverse proxy 종류와 설정 위치는 코드 레포 밖에 있으므로 배포 시 수동 반영이 필요하다.
- Google OAuth consent screen과 redirect URI 등록은 Google Cloud Console에서 별도로 수행해야 한다.
