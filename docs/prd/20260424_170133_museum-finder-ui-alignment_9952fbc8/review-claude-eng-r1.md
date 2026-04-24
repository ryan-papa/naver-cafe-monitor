# 엔지니어링 리뷰 r1

독립 서브에이전트 리뷰 — 메인 에이전트 셀프 채점 아님.

## 점수 테이블

| 항목 | 점수 | 근거 |
|------|------|------|
| 요구사항 명확성 | 8/10 | F-01~F-18이 Must/Should/Could로 우선순위 분류됨. 성공 기준·실패 모드·경로가 구체적. 단, "admin 페이지 한정" 범위(F-03)가 `/admin/*`만인지 `/login`·`/signup`도 포함인지 불명확. "프리미티브 8종"이 DataTable/PageHeader/HelpTip까지 묶여 실제 구현 단위(파일 수·props 스펙)가 열려 있음. |
| 기술적 실현가능성 | 7/10 | 스택(Astro 6.1.6 + Node adapter) 유지 방침은 정합. 다만 **참조 디자인 시스템이 전부 React `"use client"` 컴포넌트**(museum-finder/frontend/src/components/admin/primitives/*.tsx, Button·HelpTip·Input·Misc·Select 모두 "use client" 확인)이고 PRD는 "React 도입 금지" 제약을 걸고 있음. 즉 "CSS만 복사, 컴포넌트는 `.astro`로 재작성"이 되는데, Select·HelpTip·모달·포커스 트랩·쿨다운 타이머 등 상태를 가진 요소는 바닐라 JS island로 다시 구현해야 함. 이 재구현 비용·방식(Astro `<script>` 블록 vs. 별도 TS 모듈 vs. `client:load` 없는 바닐라)이 PRD에서 선언되지 않아 불확실성이 남음. |
| 범위·공수 적정성 | 7/10 | 포함/비포함 표가 대칭이고 API·배치·DB 변경 제외가 분명. 다만 **숨겨진 작업**이 다수: (1) 기존 `/` 라우트를 리다이렉트로 전환하면서 기존 페이지 내용을 `/admin/posts`로 이전해야 함, (2) `web/tests/` 부재 상태에서 Playwright + axe 초기 셋업(playwright config, axe-core 통합, CI 러너 추가), (3) `.github/workflows/ci.yml`에 현재 batch·api만 있고 **web 잡 자체가 없음** — E2E 러너 추가 필요, (4) Bootstrap 의존성 제거 여부(현 `package.json`에 `bootstrap 5.3.8` 포함) 미논의, (5) 프리미티브 재작성 외에도 `public-paths.ts`·`middleware.ts`의 리다이렉트 처리 재작성 필요. M 공수 평가가 낙관적. |
| NFR 충족도 | 8/10 | 성능(<1.5s), 접근성(axe 0, Lighthouse ≥95), 보안(세션 검증 유지), 호환성(302), FOUC(swap) 명시. 관측가능성은 "기존 유지"로 구체성 낮음. 폰트 CDN 실패 시 fallback이 "system font"로만 언급(가정 표에만 노출, NFR 섹션엔 없음). 보안 항목에 CSP/SRI — 외부 CDN 로드 시 권고되는 integrity hash·connect-src — 언급 없음. |
| 의존성·리스크 | 8/10 | 리스크 표 5종(CDN·기능 손상·세션·리다이렉트 루프·FOUC)이 검증 방법과 함께 명시. 롤백은 "feat 브랜치 revert" 수준으로 묵시적이며 PRD에 명시 롤백 섹션 없음. 폰트 CDN 장애 fallback, uvicorn 재시작 시 무중단 여부, 진행 중 세션 영향도 구체 안 됨. |
| 테스트 가능성 | 6/10 | E2E 시나리오 항목화(F-15)는 좋으나 **현재 `web/` 디렉터리에 Playwright 설치·설정 전무**(`package.json` devDeps는 vitest만, `tests/` 디렉터리 부재, CI에 web 잡 없음). 즉 "E2E 100% 통과"는 런타임 환경 구축이 전제. QA 환경 유사성(로컬 Mac Mini vs. CI ubuntu-latest) 차이 — 특히 CDN 폰트 로드·SSR 리다이렉트 검증 — 고려 부재. AC가 페이지/기능 단위로는 있지만 프리미티브 단위(예: `Select`의 키보드 탐색·포커스 링) AC가 없음. "육안 스크린샷 검증"만으로는 시각 회귀 자동화 부재. |
| **평균** | **7.33** | |

## 판정

**미달** — 평균 7.33 (< 8.0), 테스트 가능성 6점 (< 7) 두 조건 모두 위반.

## 항목별 피드백

### 요구사항 명확성 (8)
- F-03 폰트 로드 범위 "admin 한정"이 `/login`·`/signup` 포함 여부를 명시해야 함. 현재 스코프 표는 "로그인/회원가입 리디자인(폼은 유지)" 포함이라 폰트도 적용한다고 해석되지만 F-03 문구와 충돌 소지.
- F-04의 "프리미티브 8종"을 개별 F-04a~F-04h로 분해하고 각 props·variant·size 스펙을 PRD에 표로 명시하면 구현·리뷰 AC로 재사용 가능.
- S2의 쿨다운 30초 "성공 시만 적용, 실패 시 즉시 재시도" 정책을 F-10 본문에 명시(현재는 기획 피드백에만 존재).
- F-14 리다이렉트 대상이 `/`·`/settings/2fa` 2건인데, `/posts` 같은 중간 레거시 경로나 북마크 케이스를 나열/명시 필요.

### 기술적 실현가능성 (7)
- **결정적 미명시**: 참조 프리미티브 전량이 React `"use client"`인데 PRD는 React 도입 금지. 따라서 "바닐라 JS island" 구현 방식(Astro `<script is:inline>` vs. 모듈 스크립트 vs. 별도 `.ts`)과 상태 공유 패턴을 F-04 수준에서 결정 필요.
- Select·HelpTip·확인 모달 3종은 포커스 트랩·ESC 처리·aria-expanded 동기화 등 상태 코드가 필요. Astro의 `client:*` directive는 React/Vue/Svelte용이라 순수 Astro 컴포넌트에는 해당 없음 → **바닐라 JS island 패턴** 명시해야 함.
- `tokens.css`의 `oklch()` 색상 공간 사용 — Safari ≥15.4, Chrome ≥111 필요. 운영자 브라우저 범위(최신 크롬 가정인지) PRD에 명시 없음.
- Bootstrap 5.3.8이 `package.json`에 있음. 이번 리디자인에서 Bootstrap 의존성을 **제거**할지 **공존**시킬지 F-02 근방에 결정 명시 필요(토큰·프리미티브가 Bootstrap 리셋과 겹치면 스타일 충돌).

### 범위·공수 적정성 (7)
- 숨겨진 작업 다수. 다음을 F-xx로 명시할 것: **F-xx Playwright + axe 테스트 인프라 구축** (config, fixtures, CI 러너 추가), **F-xx CI workflow에 web 잡 추가** (현재 ci.yml은 batch·api만), **F-xx Bootstrap 의존성 처리 방침**, **F-xx 기존 `/` 페이지 컨텐츠의 `/admin/posts` 이관**.
- 공수 M 평가 재검토 필요. 프리미티브 8종 + 페이지 5종 + 레이아웃 셸 + E2E 인프라 + CI 잡 추가는 L로 보는 것이 안전. 또는 MVP/후속 단계를 F-18 외 하나 더 분리.
- 비-스코프에 "시각 회귀 도구 미도입" 명시된 건 좋음. 대신 육안 검증 체크리스트(로고·사이드바·테이블·버튼·모달 5항)를 F-17 근방에 명시 필요.

### NFR 충족도 (8)
- 외부 CDN(jsdelivr) 사용 → 권장 사항: CSP `style-src`·`font-src` 화이트리스트, SRI integrity hash, 실패 시 로컬 fallback 전략. NFR 보안·성능 항목에 한 줄씩 추가.
- "페이지 평균 초기 렌더 < 1.5s (로컬)"의 측정 방법(Lighthouse? 직접 계측? navigation timing?) 정의.
- 관측가능성 "기존 유지"를 구체화: 리다이렉트 302는 서버 로그 남는지, 4xx/5xx 경로 계측 경로 동일한지 한 줄 명시.

### 의존성·리스크 (8)
- **롤백 섹션 명시 필요**: "main revert + uvicorn 재시작 + `web/dist/server/entry.mjs` 재기동"까지 단계 나열. 토큰 리셋이 기존 페이지 스타일을 깨는 케이스에 대한 부분 롤백(라우트별) 가능 여부.
- NanumSquare CDN 장애 감지 시 사용자 자동 조치(시스템 폰트 대체)와 운영자 알림 경로(실패는 조용함) 분리 고려.
- Node 런타임 재시작 시 현재 접속 운영자 세션 처리(스티키 세션 아님 → 단순 재접속) 확인.

### 테스트 가능성 (6)
- **치명적**: `web/` 아래 Playwright 설치·설정·테스트 파일 전무. `package.json` devDeps에 `@playwright/test`·`axe-core`·`@axe-core/playwright` 없음. `.github/workflows/ci.yml`에 web 잡 없음. F-15·F-16이 "실행 가능"이 되려면 **사전 인프라 작업을 별도 F로 선행 명시**해야 함. CLAUDE.md 하네스 규칙 "프런트엔드 변경 시 Playwright E2E + axe 필수"가 배포 차단 조건이므로 인프라 부재는 가장 큰 리스크.
- CI 러너 환경: Playwright 브라우저 바이너리 다운로드(800MB+), `npx playwright install --with-deps` 단계 필요. self-hosted `macOS deploy` 러너 재활용 불가(PR 단계 `ubuntu-latest` 사용 중). ubuntu-latest에서 NanumSquare CDN 접근 가능 여부 확인 포인트.
- 프리미티브 단위 AC 추가: `Select` 키보드 네비(Tab/화살표/ESC), `HelpTip` aria-describedby, `Button` variant별 포커스 링 가시화. axe만으로 커버 안 되는 상호작용은 Playwright assertion으로 명시.
- 리다이렉트(302) 테스트 케이스를 F-15에 명시: `GET /` → 302 `/admin`, `GET /settings/2fa` → 302 `/admin/settings/2fa`, 체인 루프 방지 검증.
- "로컬 Mac Mini 육안 검증" 과 "CI ubuntu 자동화"의 결과 정합 전략(스크린샷 차이 허용 범위 등) 명시.

## 재작성 권고

통과 기준 충족을 위해 다음 보완 후 r2 재리뷰 권장:

1. **테스트 인프라 F 추가** (F-19·F-20·F-21 신설): Playwright 설치·config·fixture, axe 통합, CI web 잡 추가.
2. **바닐라 JS island 패턴 결정** 문서화 (Select/HelpTip/Modal/쿨다운 타이머 상태 관리 방식).
3. **Bootstrap 의존성 처리 방침**, **oklch 브라우저 지원 범위**, **CDN 실패 fallback + CSP/SRI**, **롤백 절차** 섹션 추가.
4. 프리미티브 8종 각 props·variant AC를 표로 분해.
5. 공수 재평가(M→L 검토) 또는 MVP/후속 단계 추가 분리.
