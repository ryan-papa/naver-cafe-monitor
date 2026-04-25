# QA — Google Admin Login

## 실행 결과

| 명령 | 결과 |
|---|---|
| `rtk .venv/bin/pytest api/tests shared/tests -q` | 92 passed, 5 warnings |
| `rtk npm run build` | 통과 |
| `rtk npm run test:e2e -- tests/e2e/login.spec.ts tests/e2e/primitives.spec.ts` | 4 passed |
| `rtk npm run check` | 실패: 기존 `web/src/lib/auth-client.ts` BufferSource 타입 오류 |
| `rtk npm test` | 실패: 기존 설정상 Vitest가 Playwright E2E 파일을 수집 |

## F-XX 검증

- F-01/F-02: OAuth 시작과 콜백 state 실패 테스트 추가.
- F-03/F-04: 허용 이메일 admin 승격과 미허용 이메일 차단 테스트 추가.
- F-05: 콜백 성공 경로는 `/admin/posts` 상수로 고정.
- F-06: API 테스트를 `current_admin` dependency override로 수정.
- F-07: `/login` E2E에서 401 시 OAuth 이동 검증.
- F-08: SSR 페이지에서 401/403/non-admin redirect 로직 반영.

## 디자인 QA

| 항목 | 점수 | 근거 |
|---|---:|---|
| 타이포그래피 | 8 | 기존 auth 카드 스타일 유지 |
| 컴포넌트 렌더링 | 8 | Google 로그인 링크가 단일 주요 액션으로 표시 |
| 여백·정렬 | 8 | 기존 카드 레이아웃 유지 |
| 색상·대비 | 8 | 기존 토큰 사용 |
| 반응형 | 8 | 기존 모바일 padding 규칙 유지 |
| 인터랙션 | 8 | 키보드 focus E2E 검증 |
| 접근성 | 9 | axe critical/serious 0건 |

평균: 8.1. 최저: 8.

## 잔여 리스크

- 실제 Google OAuth token 교환은 운영 client 설정이 필요해 로컬 단위 테스트에서는 mock 없이 전체 성공 플로우를 수행하지 않았다.
- 실제 서버 reverse proxy 라우팅은 배포 환경에서 별도 반영해야 한다.
