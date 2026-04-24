# PRD — museum-finder UI 정렬 (naver-cafe-monitor 전면 리디자인)

| 항목 | 값 |
|------|-----|
| 프로젝트 | naver-cafe-monitor |
| PRD ID | 20260424_170133_museum-finder-ui-alignment_9952fbc8 |
| 날짜 | 2026-04-24 |
| 브랜치 | `feat/museum-finder-ui-alignment` |
| 상태 | Approved (기획 r1 8.67 + 엔지니어링 r2 8.33, Codex 스킵) |

---

## 1. 문제·맥락

| 항목 | 내용 |
|------|------|
| 배경 | 동일 조직의 어드민 도구 `museum-finder`와 `naver-cafe-monitor` UI가 상이. 운영자가 두 시스템을 오가며 사용할 때 학습·조작 비용 발생 |
| 원인 | `naver-cafe-monitor` 가 각 페이지에 인라인 `<style>` 블록으로 디자인을 반복 정의. 토큰 없음, 프리미티브 없음, 페이지 간 간격·색상·폰트 일관성 깨짐 |
| 왜 지금 | 최근 타이포·필터·페이지네이션 정렬 개선이 산발적으로 진행됨(최근 5개 커밋 모두 style 계열). 토큰 기반 구조가 없으면 이런 땜질이 계속 누적. museum-finder는 이미 `tokens.css` 기반 디자인 시스템을 갖추고 있어 그대로 이식 가능 |

## 2. 타깃 사용자와 사용 맥락

| 항목 | 내용 |
|------|------|
| 대상 사용자 | 내부 운영자 — 네이버 카페 공지/사진 모니터링 + 알림 재발송 + 2FA 관리 담당 |
| 사용 맥락 | 데스크톱 브라우저. 업무 시간 중 처리 이력 탐색·누락 알림 재발송이 주 동선. museum-finder 어드민도 병행 사용 |
| 핵심 동기 | "museum-finder와 같은 시각으로 같은 방식으로 빠르게 탐색하고 싶다" |

## 3. 핵심 시나리오

| # | 장면 | 사용자 행동 | 시스템 반응 |
|---|------|-----------|-----------|
| S1 | 처리 이력 탐색 | `/admin/posts` 진입 → 게시판·상태 필터 선택 → 페이지네이션 이동 | museum-finder 테이블 스타일로 렌더, URL 쿼리 동기화 |
| S2 | 게시물 상세 + 재발송 | 행 클릭 → `/admin/posts/:id` 페이지 이동 → 본문·카톡 내용 확인 → "재발송" 버튼 | 상세 페이지 렌더, 재발송 성공 시 토스트 + 쿨다운(30초) |
| S3 | 2FA 설정 | 사이드바 "2FA 설정" 클릭 → `/admin/settings/2fa` 페이지 | 설정/재설정 탭 렌더 (기존 동작 유지) |
| S4 | 로그인 | `/login` 진입 → 이메일·비번·TOTP 입력 | 성공 시 `/admin` 리다이렉트 |
| S5 | 회원가입 | `/signup` 진입 → 3단계 폼 진행 | 완료 시 로그인 화면 |

**실패 모드:**

| 코드경로 | 시나리오 | 감지 방법 | UX 대응 |
|----------|----------|----------|---------|
| `GET /api/posts` | 빈 상태 | items.length===0 | 빈 상태 컴포넌트(`아이콘 + 메시지`), 페이지네이션 숨김 |
| `GET /api/posts` | 네트워크 오류 | fetch 예외 / non-2xx | 에러 배너 + 재시도 버튼 |
| `GET /api/posts/:id` | 404 | status 404 | `/admin/posts` 로 리다이렉트 + 에러 토스트 |
| `POST /api/posts/:id/resend` | 실패 | non-2xx / timeout | 상세 페이지 내 에러 토스트, 버튼 30s 쿨다운 미적용 |
| 라우팅 | 존재하지 않는 `/admin/*` | 404 페이지 | `ErrorLayout` 그대로 사용 (404) |
| 인증 | 세션 만료 | 401 | `/login` 리다이렉트 + 쿼리로 원래 경로 보존 |

## 4. 대안 탐색

### 4.1 이식 전략

| 대안 | 요약 | 장점 | 단점 | 공수 | 근거 유형 |
|------|------|------|------|------|----------|
| A (Astro 유지 + CSS 복사 + 컴포넌트 재작성) ★ | museum-finder `tokens.css` 복사, React 프리미티브를 `.astro`로 재작성 | 스택 유지, 시각 동일, 프리미티브로 유지보수 개선 | 프리미티브 재작성 공수 | M | 엔지니어 선호 |
| B (Next.js 마이그레이션) | 프레임워크 전환 후 museum-finder 컴포넌트 그대로 import | 디자인 100% 일치, 장기 통합 | 사실상 재작성, 백엔드 영향 無 여부 재검증 필요 | XL | — |
| C (단일 페이지 인라인 유지) | 기존 인라인 스타일에 museum-finder 값 넣기만 함 | 빠름 | 프리미티브化 안 됨, 반복 재발 | S | — |
| D (현상 유지) | — | 공수 0 | 원래 문제 해결 안 됨 | 0 | — |

**선택: A**  
**근거:** 엔지니어 선호 + 제품 가설(프리미티브 도입 시 후속 변경 비용 감소). 시각적 결과 동일 + 스택 영향 최소.

### 4.2 게시물 상세 UX

| 대안 | 요약 | 장점 | 단점 | 근거 유형 |
|------|------|------|------|----------|
| A (모달 유지) | 기존 모달에 new 스타일만 | 변경 최소 | 모달→페이지 결정과 충돌 | — |
| B (상세 페이지로 전환) ★ | `/admin/posts/:id` 라우트, 본문·카톡·재발송 통합 | 뒤로가기·딥링크·공유 자연스러움 | 이동 비용 소폭 증가 | 제품 가설 |

**선택: B**

### 4.3 라우팅 구조

| 대안 | 요약 | 장점 | 단점 | 근거 유형 |
|------|------|------|------|----------|
| A (`/admin/*` 재편) ★ | 대시보드·처리이력·2FA 전부 `/admin/*` 하위 | museum-finder와 구조 일치, 공개/관리 경계 명확 | 기존 URL과 호환성 없음 | 제품 가설 |
| B (현 경로 유지) | `/`, `/settings/2fa` 그대로 + 디자인만 | 기존 북마크 유지 | museum-finder와 구조 불일치 | — |
| C (A + 기존 경로 리다이렉트) | `/` → `/admin`, `/settings/2fa` → `/admin/settings/2fa` | 호환성 + 일관성 | 리다이렉트 엔트리 추가 관리 | 엔지니어 선호 |

**선택: C** — Q-D에서 A 선택했지만 내부 운영자 북마크 깨짐 방지 위해 리다이렉트 병행.

## 5. 톤·정체성

| 항목 | 정의 |
|------|------|
| 톤 | 담백·기능 중심. 어드민 도구 — 장식 최소화 |
| 어투 | 한국어 존댓말 / 기술 용어 허용 (`재발송`, `2FA`) |
| 금칙어 | 이모지, 과장 부사(`완전`, `최고`), 느낌표 연속 |
| 레퍼런스 | museum-finder Admin (`MF · Museum Finder · Admin · v1.1`), Linear, Notion Admin |
| 샘플 카피 | `처리 이력` / `전체 1,234건` / `게시물이 없습니다` |

## 6. 스코프 & 비-스코프

| 포함 (In) | 비포함 (Out) |
|-----------|-------------|
| `tokens.css` 이식 (색상·폰트·간격·라운딩·그림자) | API·배치·DB 스키마 변경 |
| Astro 프리미티브 작성: `Button`, `Input`, `Select`, `Pill`, `Icon`, `DataTable`, `PageHeader`, `HelpTip` | 신규 CRUD 기능(등록·수정) 추가 |
| 레이아웃 셸: `AppShell`, `Sidebar`, `Topbar` (메뉴 항목은 현행 유지) | 사이드바 정보구조(IR) 재편 |
| 페이지 리디자인: 대시보드 → `/admin` + 처리이력 → `/admin/posts` (현재 `/` 에 있던 테이블) | 대시보드 통계 카드 재설계 (스타일만 조정) |
| 게시물 상세 페이지 `/admin/posts/:id` | 본문 이미지 뷰어·갤러리 신규 기능 |
| 2FA 페이지 이동: `/admin/settings/2fa` | 2FA 로직 변경 |
| 로그인/회원가입 리디자인 (폼은 유지) | 인증 플로우 로직 변경 |
| 확인/알림 모달 컴포넌트 (museum-finder 스타일) | 모달 상태 관리 라이브러리 도입 |
| NanumSquare + JetBrains Mono CDN 로드 (admin-scoped) | 폰트 self-hosting |
| 기존 경로 리다이렉트 (`/` → `/admin`, `/settings/2fa` → `/admin/settings/2fa`) | 공개 페이지 경로 변경 (`/login`, `/signup` 유지) |
| Playwright E2E + axe 접근성 전체 커버 | 시각 회귀(Percy 등) 도입 |

## 7. 성공 기준 & 실패 기준

| 구분 | 지표 | 목표값 |
|------|------|--------|
| 성공 | museum-finder와 나란히 스크린샷 비교 시 구조·톤 일치 | 수동 육안 검증 통과 |
| 성공 | Playwright E2E 통과율 | 100% (목록·상세·필터·페이지네이션·재발송·2FA·로그인) |
| 성공 | axe critical/serious violations | 0건 |
| 성공 | Lighthouse 접근성 점수 (admin 페이지) | ≥ 95 |
| 성공 | 페이지 평균 초기 렌더 | < 1.5s (로컬) |
| 실패(접을 기준) | E2E 실패 건 3개 이상 또는 axe critical 1건 이상 | — |

## 8. 가정·리스크·열린 질문

| 유형 | 내용 | 검증 방법 |
|------|------|----------|
| 가정 | NanumSquare CDN(`cdn.jsdelivr.net`) 접근 가능 | 배포 환경에서 curl 테스트 |
| 가정 | 기존 인라인 스타일 제거 후에도 기능 동작 유지 | E2E 전 시나리오 통과 |
| 가정 | 대상 브라우저: Chrome ≥111, Safari ≥15.4, Firefox ≥113 (oklch 지원). 내부 운영자 기준 Chrome 최신 | 브라우저 사용자 에이전트 리포트 로그 없음 → 가정 명시 후 진행 |
| 리스크 | 세션·쿠키가 경로 변경(`/` → `/admin`)으로 무효화 | 세션 스토리지가 도메인 스코프라 무관. 로그인 후 E2E 세션 재사용 검증 |
| 리스크 | 리다이렉트 엔트리로 인한 무한 루프 | 리다이렉트 체인 Playwright 테스트 |
| 리스크 | 폰트 FOUC(NanumSquare 로드 지연) | `font-display: swap` + fallback 스택 |
| 리스크 | CDN 차단·장애 시 폰트·아이콘 미로드 | **로컬 폰트 파일 fallback 없음(1차)**. 운영 관찰 후 필요 시 self-host로 전환 |
| 리스크 | Bootstrap 5.3.8 리셋과 museum-finder 토큰·`.mf-admin` 스타일 충돌 | **Bootstrap 전역 import 제거** (F-22). 개별 컴포넌트에서 필요한 유틸만 직수입 |
| 리스크 | Playwright CI 잡 추가 시 빌드 시간 증가 (brower install 800MB+) | `actions/cache`로 `~/.cache/ms-playwright` 캐시, Chromium 단일 브라우저로 제한 |
| 열린 질문 | 로고 이니셜 `NC` vs `CM`(현행) | `NC · Naver Cafe Monitor` 로 확정(Q9) |
| 열린 질문 | 다크모드 지원 범위 | museum-finder가 이미 `[data-theme="dark"]` 제공 → 토큰만 복사, UI 토글은 추후 과제 |

## 8-A. 바닐라 JS Island 패턴 (기술 결정)

참조 프리미티브는 React `"use client"` 컴포넌트인데 본 프로젝트는 **Astro 순정 유지** 제약이 있음. 상태가 필요한 요소(Select 드롭다운·HelpTip 토글·모달 포커스 트랩·재발송 쿨다운 타이머)는 **바닐라 JS island** 패턴으로 재구현한다.

| 패턴 | 사용 케이스 | 구현 방식 |
|------|------------|----------|
| 순수 마크업(JS 없음) | Button·Pill·PageHeader·DataTable | `.astro` 단일 파일 |
| `<script>` (페이지 로컬) | 페이지 전용 인터랙션(필터 제출, 페이지네이션 이동) | `.astro` 내 `<script>` 블록 (Astro가 ESM 번들링) |
| 독립 TS 모듈 + `<script src>` | 재사용 island(Modal·Select·HelpTip·ResendButton) | `web/src/islands/<name>.ts` + `<script src={...}>` 인클루드 |
| data-attribute 훅 | island가 DOM을 찾을 때 | `data-island="modal"` 등 속성 기반 쿼리셀렉터 |

**상태 공유:** 페이지 레벨 `window` 전역 금지. 모듈 스코프 변수 + `CustomEvent` 버스로 교차 통신.  
**포커스 트랩 라이브러리:** `focus-trap` 선택 (4KB, 의존성 無). 또는 직접 구현.  
**쿨다운 타이머:** `localStorage` 에 `resend:{postId}:cooldownUntil` 저장, 페이지 이동 후 복귀 시 남은 시간 복원.

## 8-B. 성능·보안 세부 (NFR 보강)

| 항목 | 내용 |
|------|------|
| 성능 측정 | Lighthouse(모바일 에뮬레이션 off, 데스크탑 프리셋) + `navigation` 타이밍. `/admin` 첫 로드 기준 |
| 렌더 목표 | TTFB < 300ms, FCP < 1.0s, LCP < 1.5s (로컬) |
| 관측가능성 | Astro 미들웨어에서 리다이렉트 302 발생 시 `console.info` 로그 (운영 로그 집계 유지). 4xx/5xx 경로는 기존 `ErrorLayout` 진입 시 동일 포맷 유지 |
| CSP | `style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; font-src 'self' cdn.jsdelivr.net data:; script-src 'self' 'unsafe-inline'` — admin 한정. 공개 페이지는 기존 정책 유지 |
| SRI | jsdelivr 로드되는 `pretendard`(제거), `nanum`, `bootstrap-icons` 링크 태그에 `integrity`·`crossorigin="anonymous"` 속성 추가 |
| 빌드 경고 | Astro 빌드 warn/error 0건 목표. `astro check` 타입 검증 통과 |

## 8-C. 롤백 절차

| 단계 | 조치 |
|------|------|
| 1 | `git revert <머지 커밋>` 또는 main 이전 태그로 revert PR |
| 2 | `cd web && npm ci && npm run build` 재빌드 |
| 3 | `node web/dist/server/entry.mjs` 재기동 (uvicorn·nginx·cron 불변) |
| 4 | `curl -sI http://127.0.0.1:4321/ | head -1` 로 200/302 확인 |
| 부분 롤백 | 토큰만 문제 시 `web/src/styles/tokens.css` 복원 + globals.css 이전 상태 체크아웃 |
| 감지 | 운영자 보고(Slack·이메일) + 서버 로그 500 스파이크 |

---

## 9. 기능 요구사항

### 9-1. 스타일 / 토큰 기반

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| F-01 | museum-finder `tokens.css` 를 `web/src/styles/tokens.css` 로 이식. Light + Dark 토큰 전부 | Must |
| F-02 | 전역 리셋·`.mf-admin` 스코프 스타일을 `web/src/styles/globals.css` 에 이식 | Must |
| F-03 | NanumSquare(`.mf-admin` 스코프) + JetBrains Mono(mono 토큰) CDN 로드. 적용 범위: `/admin/*` + `/login` + `/signup` (모든 내부 화면). 링크 태그는 공용 레이아웃에 배치, `font-display: swap` 명시 | Must |
| F-22 | `package.json` 에서 `bootstrap` 전역 import 제거. `bootstrap-icons`는 유지(아이콘 `<i class="bi bi-*">` 계속 사용) 또는 museum-finder의 `Icon.astro` SVG로 전량 대체 중 **후자 채택**. `bootstrap` devDeps·런타임 제거 후 번들 사이즈 검증 | Must |

### 9-2. 프리미티브 컴포넌트 (Astro)

| ID | 컴포넌트 | props·variant 스펙 | AC |
|----|---------|------|-----|
| F-04a | `Button.astro` | variant: `default`/`primary`/`ghost`/`danger`/`subtle`, size: `sm`/`md`/`lg`, `icon`/`iconRight`, `active`, `disabled` | 포커스 링 `outline: 2px solid var(--accent)`. 키보드 Enter/Space 활성화 |
| F-04b | `Input.astro` | size: `sm`/`md`, `icon` 슬롯, native input props 전달 | 아이콘 + input 정렬, `aria-invalid`·에러 스타일 |
| F-04c | `Select.astro` | size: `sm`/`md`, options: `string[]` or `{value,label}[]`, 커스텀 화살표 SVG | Tab 포커스, 화살표 키 네비, ESC 닫기, `aria-expanded` 동기화 (native select 사용 시 브라우저 기본 동작) |
| F-04d | `Pill.astro` | tone: `success`/`warning`/`danger`/`info`/`neutral`/`accent`, size: `sm`/`md` | tone별 `-soft`/`-border` 토큰 조합, `role="status"` 선택 적용 |
| F-04e | `Icon.astro` | name: 22종(search/plus/check/chevR/L/U/D/home/database/merge/trash/alert/inbox/close/edit/save/…), size, stroke | SVG `stroke="currentColor"`. aria-hidden 기본, `label` props 시 `aria-label` |
| F-04f | `DataTable.astro` | columns: `{key,label,align?,render}`, rows, emptyText, caption | `<caption class="sr-only">` 필수. 행 호버 `var(--bg-hover)` 전환 90ms |
| F-04g | `PageHeader.astro` | title, subtitle?, actions? (슬롯) | h1 `fontSize:17`, 하단 보더, actions flex 정렬 |
| F-04h | `HelpTip.astro` | tip 텍스트 or 슬롯 | `?` 원형 버튼, 클릭 토글. ESC 닫기, `role="tooltip"`, `aria-describedby` 연결 |

### 9-3. 레이아웃 셸

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| F-05 | `AppShell.astro` — `<div display:flex height:100dvh>` + `<Sidebar/>` + `<div flex:1><Topbar/><main>{slot}</main></div>` | Must |
| F-06 | `Sidebar.astro` — 로고 `NC` + `Naver Cafe Monitor` + `Admin · v{pkg.version}`. 섹션: 개요(대시보드) / 모니터링(처리 이력, 알림 큐) / 시스템(2FA, 배치 이력). 현재 비활성 메뉴는 `opacity:0.5 cursor:not-allowed` | Must |
| F-07 | `Topbar.astro` — 우측 이메일(`--fs-13 --fg-muted`) + 로그아웃 버튼 (`size=sm, variant=ghost`) | Must |

### 9-4. 페이지

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| F-08 | `/admin/index.astro` 대시보드 — 통계 카드(전체/성공/실패) + 최근 활동 요약. museum-finder 스타일 | Must |
| F-09 | `/admin/posts/index.astro` 처리 이력 목록 — `PageHeader` + 필터(게시판/상태/정렬) + 페이지네이션 + `DataTable`. URL 쿼리 `?board&status&sort&order&page&size` 동기화 | Must |
| F-10 | `/admin/posts/[id].astro` 게시물 상세 — 본문·카톡 내용·재발송 버튼. **쿨다운 30초(성공 시만 적용, 실패 시 즉시 재시도 가능)**. 404 시 `/admin/posts` 리다이렉트 + 에러 토스트 | Must |
| F-11 | `/admin/settings/2fa.astro` — 기존 로직 이식(초기 설정/재설정 탭, QR 표시, 백업 코드). 모달 섹션은 museum-finder 스타일 | Must |
| F-12 | `/login` + `/signup` — museum-finder 카드 스타일. 폼 로직·검증 기존 유지 | Must |
| F-17 | `ErrorLayout.astro` 리스타일 — 401/403/404/500/offline 모두 새 토큰 적용 | Should |
| F-18 | 다크모드 토큰 이식(`[data-theme="dark"]`). 토글 UI 미도입 | Could |

### 9-5. 공통 컴포넌트 / 미들웨어

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| F-13 | `Modal.astro` + `islands/modal.ts` — museum-finder 스타일 확인/알림 모달. 포커스 트랩(`focus-trap` 4KB lib), ESC 닫기, backdrop 클릭 닫기, `aria-modal`·`role=dialog` | Must |
| F-14 | 리다이렉트 — `web/src/middleware.ts` 에 엔트리 추가: `/` → `/admin` (302), `/settings/2fa` → `/admin/settings/2fa` (302). 체인 루프 방지 가드 | Must |

### 9-6. 테스트 인프라

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| F-19 | `web/` 에 Playwright 설치 + `playwright.config.ts` 작성 (Chromium 단일, baseURL 환경변수, reporter HTML) + `web/tests/e2e/` 디렉터리 생성 | Must |
| F-20 | `@axe-core/playwright` 통합 — 각 페이지 테스트 말미에 `await expect(await new AxeBuilder({ page }).analyze()).toHaveNoViolations({ impactLevels: ['critical', 'serious'] })` | Must |
| F-21 | `.github/workflows/ci.yml` 에 `web` 잡 추가 — Node 22, `npm ci`, `astro check`, `astro build`, `npx playwright install --with-deps chromium` (캐시 키 `~/.cache/ms-playwright`), `npx playwright test`. 실패 시 `test-results/` 아티팩트 업로드 | Must |
| F-23 | 프리미티브 단위 AC E2E — `Select` 키보드 네비, `HelpTip` ESC 닫기·`aria-describedby` 존재, `Modal` 포커스 트랩 | Must |
| F-24 | 리다이렉트 E2E — `GET /` → 302 `/admin`, `GET /settings/2fa` → 302 `/admin/settings/2fa`, 체인 없음 확인 | Must |
| F-25 | 육안 검증 체크리스트 (`docs/qa/visual-check.md`) — 로고·사이드바·테이블·필터·페이지네이션·모달·배지·폰트·아이콘 9항 | Should |

## 10. 비기능 요구사항

| 항목 | 요구사항 |
|------|----------|
| 성능 | `/admin` 첫 로드 TTFB < 300ms, FCP < 1.0s, LCP < 1.5s (로컬). Lighthouse 접근성 ≥ 95. 폰트 `font-display: swap` |
| 보안 | 인증 미들웨어 유지. CSP — admin: `style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; font-src 'self' cdn.jsdelivr.net data:` 명시. 외부 CSS/폰트 링크에 `integrity`·`crossorigin="anonymous"` |
| 접근성 | axe critical/serious 0건, 키보드 네비게이션 전 경로 가능, 포커스 링 가시화(`outline: 2px solid var(--accent)`). 포커스 트랩 모달 검증 |
| 관측가능성 | Astro 미들웨어 리다이렉트 302 `console.info` 로그. 빌드 시 `astro check` 통과. CI 실패 시 Playwright trace 아티팩트 업로드 |
| 호환성 | 브라우저: Chrome ≥111, Safari ≥15.4, Firefox ≥113 (oklch). 기존 북마크 `/`·`/settings/2fa` 302 리다이렉트로 보존 |
| 국제화 | 한국어 단일 (기존 동일) |

## 11. 기술 스택 · 제약사항

| 항목 | 내용 |
|------|------|
| 기술 스택 | Astro 6.1.6 (SSR, Node adapter), 바닐라 JS island 패턴, CSS 토큰(oklch) + `.astro` 프리미티브 + `focus-trap` |
| 폰트 | NanumSquare (CDN, admin + 로그인/회원가입), JetBrains Mono (CDN) — 제거 대상: Pretendard(기존) |
| 아이콘 | museum-finder `Icon.astro` SVG 전량 이식. `bootstrap-icons` 제거 |
| 기술 제약 | React 도입 금지 (`@astrojs/react` 미도입). Svelte·Vue도 미도입 |
| 기술 제약 | 백엔드 API·DB 스키마·배치 변경 불가 |
| 공수 재평가 | **L** (초기 **M** 에서 상향) — 프리미티브 8종 + 페이지 7종 + 레이아웃 셸 + 미들웨어 + E2E 인프라 + CI 잡 + Bootstrap 제거 + 아이콘 전환 종합 |
| 비즈니스 제약 | 로컬 Mac Mini 배포 환경, 기존 uvicorn·nginx·cron 영향 0 |
| 검증 | CI 필수 통과, Playwright + axe 통과, 서브에이전트 기획/엔지니어 리뷰 평균 ≥ 8.0 (항목별 ≥ 7) |

---

## Review 결과

### 기획 리뷰 (Planning Review)

| 회차 | 명확성 | 완성도 | 실현가능성 | 일관성 | 측정가능성 | 경계 명확성 | 분기 충분성 | 사용자 검증 게이트 | 대안 탐색 | 평균 |
|------|--------|--------|-----------|--------|-----------|-----------|-----------|-------------------|----------|------|
| 1 | 9 | 9 | 9 | 9 | 9 | 9 | 8 | 8 | 8 | **8.67** |

**판정:** 통과 / 10
**피드백:** 전 항목 ≥ 8. 상세는 `review-claude-plan-r1.md` 참조

### 엔지니어링 리뷰 (Engineering Review)

| 회차 | 요구사항 명확성 | 기술적 실현가능성 | 범위·공수 | NFR | 의존성·리스크 | 테스트 가능성 | 평균 |
|------|---------------|-----------------|----------|-----|-------------|-------------|------|
| 1 | 8 | 7 | 7 | 8 | 8 | 6 | 7.33 (미달) |
| 2 | 9 | 8 | 8 | 9 | 8 | 8 | **8.33** (통과) |

**판정:** 통과 / 10
**피드백:** r1 9개 블로커 전부 반영 완료. 상세는 `review-claude-eng-r1.md`·`review-claude-eng-r2.md` 참조

### Codex 리뷰

- 기획 리뷰: **스킵** — 2026-04-24 17:05 `codex exec` 실행 시 `You've hit your usage limit. try again at 8:22 PM` 응답. 사용자 승인으로 스킵, 하네스 규칙 개정을 회고 단계에서 반영 예정
- 엔지니어링 리뷰: 스킵 (동일 사유)
- 코드 리뷰: 스킵 (동일 사유)

### 최종 판정

**Approved** — 기획 r1 8.67 + 엔지니어링 r2 8.33 통과. Codex 리뷰는 사용량 한도로 스킵(승인 받음).
