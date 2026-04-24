# 코드 리뷰 r1 (Claude 서브에이전트)

| 항목 | 값 |
|------|-----|
| 브랜치 | `feat/museum-finder-ui-alignment` |
| 베이스 | `main` |
| 커밋 수 | 4 (PRD/토큰 · 프리미티브·레이아웃 · 페이지·리디자인 · E2E) |
| 변경 규모 | 46 files, +4900 / -1750 |
| 리뷰어 | 독립 서브에이전트 (메인 에이전트 셀프 채점 아님) |

## 점수 테이블

| # | 항목 | 점수 | 근거 |
|---|------|------|------|
| 1 | 정확성 | 8 | SSR fetch 3경로 모두 try/catch + null fallback, 404 별도 분기(`"notfound"`), post id 정규식 가드(`/^\d+$/`), size 화이트리스트(`VALID_SIZES`), `legacyTarget !== pathname` 가드로 루프 방지, page/size 경계값(startN=0, atLast) 정확. 감점 사유: (a) 미들웨어 `fetchMe`가 비-JSON 응답에 대해 `r.json()` 실패 시 catch로 null 처리는 되지만 `totp_setup_required` 없는 구 사용자도 동작은 문제 없음 (b) `/api/auth/me` 요청에서 access_token 쿠키만 전달하고 CSRF/refresh 쿠키는 forward하지 않음 — 현 시점 인증 회귀 없음으로 판단하지만 PR에 명시 필요. 1a N/A: write 경로는 `POST /api/posts/:id/resend` 1건, 동시성 write 없음(GET 위주 SSR). 1b N/A: Astro 스택 — 프록시 어드바이스·self-invocation 개념 없음 |
| 2 | 설계 및 구조 | 9 | `primitives/` 8종 + `admin/` 4종 + `islands/` 3종 + `styles/tokens.css` 토큰으로 책임 경계 명확. Modal은 템플릿(`Modal.astro`) + 제어(`islands/modal.ts`) 분리, Pagination은 선언적 props + 내장 script로 URL 동기화만 담당. AppShell이 Topbar+Sidebar+main grid를 캡슐화해서 모든 admin 페이지에 재사용. 감점 최소: 미들웨어 `LEGACY_REDIRECTS`가 미들웨어 안에 인라인 상수로 남아있는데 `lib/public-paths.ts`와 대칭 위치 파일로 빼면 더 좋음 (개선 제안 수준) |
| 3 | 가독성 | 9 | 모든 프리미티브/페이지 파일 상단에 `/** 파일 역할 */` 주석 + props 설명. `.astro` 파일 props interface를 명시. 상수는 SCREAMING_SNAKE(`COOLDOWN_MS=30_000`, `VALID_SIZES`, `DEFAULT_SIZE`, `SETUP_PATH`). `splitKakaoBlocks` 함수 주석에 "왜" 설명. Icon 파일에 PATHS 레코드로 아이콘 22종 가독성 있게 정리. 페이지 내 CSS는 scoped style로 이름 충돌 회피 |
| 4 | 테스트 품질 | 8 | 14 스펙이 Happy/Sad 균형 있게 분포: 프리미티브 2건(Button keyboard Enter, Input focus-within), login 3건(render/validation/a11y), error 4건(404/500 × render+a11y), redirects 4건(302 위치 + follow 후 `/login?next=` 확인), home-redirect 1건. 302 체인을 `maxRedirects:0` 으로 분해 검증하는 방식 탁월. `runA11y` 헬퍼가 critical/serious만 필터해 axe 결과의 노이즈 감소. 감점 사유: (a) 프리미티브 스펙 주석에 자인하듯 Select 키보드 네비·HelpTip ESC·Pagination next/prev 클릭·Modal focus-trap 순환 등 인증 벽 뒤 기능은 미커버 — 후속 배치로 미뤄져 있음 (b) resend-cooldown 30초 쿨다운/localStorage 지속성 단위 테스트 부재 |
| 5 | 보안 | 9 | `Icon.astro`의 `set:html`는 **정적 상수 `PATHS`의 타입 좁혀진 키(`IconName` union)로만 주입** — 사용자 입력 경로 없음, XSS 위험 없음. 모달·토스트 모두 `textContent` 사용(`resend-cooldown.ts:28, el.textContent = msg`). `rel="noopener noreferrer"` 적용(`[id].astro:153`). 미들웨어 기본 deny(`isPublic` 아닌 경로는 access_token 필수) 유지, 인증 로직 우회 없음. SSR fetch 시 원본 쿠키를 그대로 forward하므로 백엔드 세션·CSRF 검사에 영향 없음. 감점 사유: (a) `BaseHead.astro`에서 jsdelivr CDN 폰트 CSS를 **SRI 없이** 로드 — PRD 4·5장에 "CSP/SRI" 언급이 있으나 실제 구현 누락. 내부 어드민(robots noindex)이라 위험도 낮음이지만 향후 CSP 강화 시 필수. (b) `/admin/posts/:id` 에러 시 `{ detail?: string }` 를 그대로 `toast`로 노출 — 백엔드가 스택/경로 노출하지 않는다는 신뢰에 의존 |
| 6 | 성능 | 8 | SSR fetch 2건 `Promise.all` 병렬화, 페이지네이션 size 상한 100으로 제한, tokens.css/globals.css 합쳐 173줄로 경량. 감점 사유: (a) 각 admin 페이지가 `fetchMe` 중복 호출 — 미들웨어가 이미 호출한 결과를 컨텍스트(`context.locals`)에 재사용하도록 리팩토링하면 페이지당 1 round-trip 절감 가능 (b) 제목 검색 `q`가 **현재 페이지 items 안에서만 클라이언트 필터**(주석에 명시) — 전체 대비 잘못된 count 표시 위험은 없으나 UX 제약으로 PRD에 명시된 "API 미지원" 범위 내 허용 (c) jsdelivr CDN 폰트 preconnect 적용(good)이지만 CDN 장애 시 FOUT |
| 7 | 유지보수성 | 9 | 4 커밋 체크포인트(8d0d2ea PRD+tokens, 58996e5 프리미티브+레이아웃+모달, 71de9a3 페이지 리디자인, c6cd32f E2E) 각 의미 단위로 분리되어 bisect 가능. 커밋 메시지 컨벤션 일관(`chore/feat/test(ui|web)`). tokens.css 중앙 집중으로 향후 테마 변경 한 곳. `package.json`에서 bootstrap 제거 + focus-trap 추가로 deps 슬림. `.github/workflows/ci.yml` 에 web 잡 추가 + Playwright 캐시 + 실패 시 artifact 업로드 — CI 회귀 탐지 기반 마련 |
| **평균** | **8.57** | |

## 판정

**통과** — 평균 8.57, 각 항목 ≥ 8. 1b FAIL 해당 없음(Astro 스택).

## 1a / 1b 명시

- **1a N/A**: 동시성 write 경로 없음. 쓰기는 `POST /api/posts/:id/resend` 단일 경로이며 클라이언트는 30초 쿨다운(localStorage) + `button.disabled` 이중 가드로 중복 클릭을 막음. 서버 단 Idempotency 키는 백엔드 범위(본 PR 변경 없음). SSR 페이지는 전부 GET
- **1b N/A**: Astro 스택 — SDK·프록시 어드바이스·self-invocation 개념이 존재하지 않음. 미들웨어는 `defineMiddleware` 1건 + public-paths 가드만 존재

## High 이슈 (배포 블로킹)

없음.

## Mid 이슈 (머지 후 후속 티켓 권장)

| # | 위치 | 내용 | 제안 |
|---|------|------|------|
| M1 | `web/src/middleware.ts` + `web/src/pages/admin/**/*.astro` | 미들웨어와 각 admin 페이지가 `/api/auth/me` 를 **중복 호출**(페이지 진입당 2회). | `context.locals.me` 에 1회 캐시해서 페이지에서 재사용. Astro 미들웨어 표준 패턴 |
| M2 | `web/src/components/BaseHead.astro` | jsdelivr CDN 폰트 CSS를 **SRI integrity 없이** 로드. PRD 4·5장에 "CSP/SRI" 언급 있음. | `integrity="sha384-..." crossorigin="anonymous"` 추가 또는 폰트를 self-host로 전환 |
| M3 | `web/src/pages/admin/posts/[id].astro:83` | `err.detail` 을 토스트에 그대로 노출. | 백엔드가 안전한 메시지만 반환한다는 전제를 명문화하거나 화이트리스트 매핑 |

## Low 이슈 (선택적 개선)

| # | 위치 | 내용 | 제안 |
|---|------|------|------|
| L1 | `web/tests/e2e/primitives.spec.ts` | 인증 벽 뒤 프리미티브(Select 키보드·HelpTip ESC·Modal focus-trap 순환·Pagination next/prev) 미커버. | 테스트 전용 `/admin/_components-demo` 라우트(dev only) 또는 Playwright에서 미들웨어 우회용 fixture 추가 |
| L2 | `web/src/islands/resend-cooldown.ts:45` | 쿨다운 key가 `resend:${postId}:cooldownUntil` — **앱 네임스페이스 prefix 없음**. 동일 도메인에 다른 앱이 mount되면 충돌 가능(현재는 문제 없음). | `ncm.resend:${postId}` 형태로 prefix 부여 |
| L3 | `web/src/pages/admin/posts/[id].astro:357` | `padding-top: 4px;` + `padding-top: 12px;` CSS 중복 선언. | 4px 삭제 |
| L4 | `web/src/middleware.ts:7-10` | `LEGACY_REDIRECTS` 상수가 미들웨어에 인라인 고정. | `lib/legacy-redirects.ts` 로 분리해 `isPublic` 과 대칭 |

## 개선 제안 (후속 PR 권장)

1. **M1 me 캐시**: `src/env.d.ts` 에 `App.Locals.me` 타입 선언 → 미들웨어에서 `context.locals.me = me` 세팅 → 페이지는 `Astro.locals.me` 사용. 페이지당 round-trip 1회 절감 + 일관된 인증 상태
2. **M2 CSP/SRI**: `astro-critters` 또는 `fontsource` self-host 적용 — CDN 의존 제거 + integrity 보장 + 오프라인 안정성. 또는 별도 admin-only로서 CSP header를 Response 후처리로 주입(`frame-ancestors 'none'`, `default-src 'self'` 등)
3. **L1 프리미티브 데모 라우트**: `/admin/_demo` 를 dev 전용으로 열고 Playwright 가 쿠키 셋업 후 방문. Select/HelpTip/Modal/Pagination E2E 전부 커버 가능

## 증거 체크

- Playwright 14 tests: 테스트 파일 기준 개수 확인 — primitives 2 + login 3 + error 4 + redirects 4 + home-redirect 1 = **14건** 일치
- Icon set:html 안전성: `IconName` TypeScript union 타입이 컴파일 타임에 키를 강제, PATHS 상수는 정적 SVG 문자열만 포함 — XSS 불가능
- 미들웨어 무한 루프 방지: `legacyTarget && legacyTarget !== pathname` 가드 + `isPublic` 우회 경로 분리
- CI 추가: ubuntu-latest + Node 22 + npm ci + astro build + playwright install + playwright test + failure artifact

## 최종 결론

- **판정: 통과**
- **평균: 8.57**
- **High 이슈: 없음** — 머지·배포 진행 가능
- Mid/Low 이슈는 후속 PR 또는 회고 액션 아이템으로 트래킹 권장
