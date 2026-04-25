# Task List: naver-cafe-monitor

**PRD:** `docs/prd/20260411_120000_naver-cafe-monitor_b7e2c9f4.md`
**세션:** b7e2c9f4

| ID | 설명 | PRD | 우선순위 | 상태 | 브랜치 |
|----|------|-----|----------|------|--------|
| T-01 | 프로젝트 초기 구조 + 의존성 설정 (pyproject.toml, Docker) | - | High | Done | `feat/T-01-project-setup` |
| T-02 | 설정 관리 (config.yaml + .env 기반 인증정보) | F-09, F-10 | High | Done | `feat/T-02-config` |
| T-03 | 네이버 카페 로그인 + 게시판 크롤러 (Playwright) | F-01 | High | Done | `feat/T-03-crawler` |
| T-04 | 새 게시물 감지 (마지막 확인 ID 비교) | F-02 | High | Done | `feat/T-04-post-detection` |
| T-05 | 이미지 다운로더 (일반 게시판) | F-03 | High | Done | `feat/T-05-image-downloader` |
| T-06 | 얼굴 인식 기준 이미지 등록 CLI | F-05 | High | Done | `feat/T-06-T-07-face` |
| T-07 | 얼굴 인식 필터링 (기준 이미지 비교) | F-04 | High | Done | `feat/T-06-T-07-face` |
| T-08 | 공지사항 텍스트 추출 | F-06 | High | Done | `feat/T-08-T-09-notice-summary` |
| T-09 | AI 요약 (일정 포함) | F-07 | High | Done | `feat/T-08-T-09-notice-summary` |
| T-10 | 카카오톡 1:1 메시지 전송 (PyKakao) | F-08 | High | Done | `feat/T-10-kakao-bot` |
| T-11 | 폴링 스케줄러 (주기·ON/OFF) | F-09, F-10 | Mid | Done | `feat/T-11-T-12-T-13-scheduler` |
| T-12 | 재시도 로직 + 오류 로그 | F-11 | Mid | Done | `feat/T-11-T-12-T-13-scheduler` |
| T-13 | 플러그인 구조 (게시판 유형 확장) | F-12 | Mid | Done | `feat/T-11-T-12-T-13-scheduler` |

## 카카오 토큰 자동 갱신

**PRD:** `docs/prd/20260413_202128_kakao-token-auto-refresh_k7m3x9p2.md`

| ID | 설명 | PRD | 우선순위 | 상태 | 브랜치 |
|----|------|-----|----------|------|--------|
| T-14 | `KakaoAuth` 클래스 + `config/kakao_token.json` 토큰 관리 (로드/저장/갱신) | F-13, F-14, F-16 | High | Done | `feat/T-14-kakao-auth` |
| T-15 | `Config` 마이그레이션: `KAKAO_TOKEN` → `KAKAO_CLIENT_ID`/`SECRET` + `KakaoMessenger` 리팩터링 | F-21, F-22 | High | Done | `feat/T-15-config-migration` |
| T-16 | 401 감지 → 토큰 갱신 → 재시도 로직 (`KakaoMessenger` + `KakaoAuth` 통합) | F-15 | High | Done | `feat/T-16-401-retry` |
| T-17 | refresh token 만료 알림 (WARNING 로그 + 카카오톡, 하루 1회, 14일 전부터) | F-17, F-18, F-19 | Mid | Done | `feat/T-17-refresh-alert` |
| T-18 | `scripts/kakao_setup.py` 셋업 스크립트 (로컬 서버 + 브라우저 + 토큰 발급) | F-20 | Mid | Done | `feat/T-18-kakao-setup` |

## DB 전환 및 3-Tier 구조 재구성

**PRD:** `docs/prd/20260415_214833_db-migration_6a3a6246.md`
**통합 브랜치:** `feat/db-migration`

| ID | 설명 | PRD | 우선순위 | 상태 | 브랜치 |
|----|------|-----|----------|------|--------|
| T-19 | 모노레포 구조 재구성 — `src/` → `batch/src/`, `api/`, `web/`, `db/`, `shared/` 생성, import 경로 수정 | F-09 | High | Done | `feat/T-19-monorepo-restructure` |
| T-20 | DDL 작성 + DB/테이블 생성 — `db/ddl.sql`, eepp.shop MySQL 실행 | F-01, F-02 | High | Done | `feat/T-20-ddl-posts-table` |
| T-21 | shared DB 연결 모듈 — `shared/database.py` SSL 기반 연결 풀 | F-10 | High | Done | `feat/T-21-shared-db-connection` |
| T-22 | batch DB 기록 — 게시글 처리 시 `posts` INSERT, status(SUCCESS/FAIL) | F-03 | High | Done | `feat/T-22-batch-db-insert` |
| T-23 | DbStore 구현 — `LastSeenStore` Protocol DB 구현체, `MAX(post_id)` 조회 | F-04 | High | Done | `feat/T-23-db-store-impl` |
| T-24 | 마이그레이션 스크립트 — `last_seen.json` → DB import 후 파일 삭제 | F-05 | High | Done | `feat/T-24-migrate-last-seen` |
| T-25 | FastAPI 백엔드 — `GET /api/posts` (필터/정렬/페이징), `GET /api/posts/{id}` | F-06, F-07 | High | Done | `feat/T-25-fastapi-backend` |
| T-26 | Astro 프론트엔드 — 게시글 이력 목록 페이지 (테이블형, 필터/정렬/페이징) | F-08 | High | Done | `feat/T-26-astro-frontend` |

### 의존성 그래프

```
T-19 (모노레포 구조)
 ├── T-20 (DDL)
 └── T-21 (DB 연결)
      ├── T-22 (batch DB 기록)
      ├── T-23 (DbStore)
      ├── T-24 (마이그레이션)
      └── T-25 (FastAPI)
           └── T-26 (Astro 프론트)
```

## 대시보드 디자인 개선 + 카톡 재발송

**PRD:** `docs/prd/20260416_150000_dashboard-redesign-resend_a4f8k2m7.md`
**통합 브랜치:** `feat/dashboard-redesign-resend`

| ID | 설명 | PRD | 우선순위 | 상태 | 브랜치 |
|----|------|-----|----------|------|--------|
| T-27 | 대시보드 CSS 모노크롬 리디자인 | F-01~F-06 | High | Todo | `feat/dashboard-redesign-resend` |
| T-28 | 재발송 API 엔드포인트 구현 | F-08~F-10 | High | Todo | `feat/dashboard-redesign-resend` |
| T-29 | 프론트엔드 재발송 버튼 + 토스트 + 쿨다운 | F-07, F-11, F-12 | High | Todo | `feat/dashboard-redesign-resend` |
| T-30 | 테스트 작성 | F-08~F-10 | High | Todo | `feat/dashboard-redesign-resend` |

### 의존성 그래프

```
T-27 (CSS 리디자인) ─────────────────┐
T-28 (재발송 API) ──┬── T-29 (프론트) ├── 완료
                    └── T-30 (테스트) ┘
```

## 대시보드 페이지네이션 + 상세 모달

**PRD:** `docs/prd/20260417_195324_dashboard-pagination-detail-modal_ce169293.md`
**통합 브랜치:** `feat/dashboard-pagination-detail-modal`

| ID | 설명 | PRD | 우선순위 | 상태 | 브랜치 |
|----|------|-----|----------|------|--------|
| T-31 | 페이지네이션 UI (맨앞/앞/번호±2/뒤/맨뒤) + 페이지크기 Select(10/30/50, 기본 30) + 상태 관리 + API offset/limit 연동 + 빈 상태·범위 초과 처리 | F-01, F-02, F-09 | High | Todo | `feat/T-31-pagination` |
| T-32 | 게시물 상세 모달 — 본문 영역 (제목·날짜·요약·원본 URL) + 열기/닫기/ESC/배경 클릭 + 포커스 트랩 | F-03, F-04, F-07 | High | Todo | `feat/T-32-detail-modal` |
| T-33 | 모달 내 카카오톡 전송 내용 재구성 (`send_notice_summary` 포맷 모사, `[일정 정리]` 분리 2블록) + 단위 테스트 | F-05 | High | Todo | `feat/T-33-kakao-render` |
| T-34 | 재발송 버튼 모달로 이동 + 기존 리스트 행 버튼 제거 (SUCCESS 상태만 활성, 로딩/에러 처리) | F-06 | High | Todo | `feat/T-34-resend-relocate` |
| T-35 | URL 상태 동기화 (`?page=N&size=S`) — 새로고침·뒤로가기 복원 | F-08 | Mid | Todo | `feat/T-35-url-sync` |

### 의존성 그래프

```
T-31 ──┬── T-32 ──┬── T-33
       │          └── T-34
       └── T-35
```

## 카카오 토큰 주기 선제 갱신 (3시간 cron)

**PRD:** `docs/prd/20260424_111935_kakao-token-scheduled-refresh_s3c9n7r4.md`
**통합 브랜치:** `feat/kakao-token-scheduled-refresh`

| ID | 설명 | PRD | 우선순위 | 상태 | 브랜치 |
|----|------|-----|----------|------|--------|
| T-36 | `KakaoAuth` 파일 락 + 재로드·머지 패턴 (fcntl.flock, 볼러틸 필드 화이트리스트) + 프로세스간 테스트 | F-29 | High | Done | `feat/kakao-token-scheduled-refresh` |
| T-37 | `batch/src/kakao_refresh.py` 엔트리 모듈 + 토큰 마스킹 로거 + 전용 로그 파일 (`batch/logs/kakao_refresh.log`) | F-23, F-24, F-27 | High | Done | `feat/kakao-token-scheduled-refresh` |
| T-38 | `install_cron.sh` 2-entry 확장: refresh 엔트리 추가, 마커 분리, `--uninstall=<refresh\|batch\|all>` 파싱, 재실행 멱등성 | F-25, F-26 | High | Done | `feat/kakao-token-scheduled-refresh` |
| T-39 | 테스트: `test_kakao_refresh.py` (성공/실패/마스킹), `test_kakao_auth_lock.py` (multiprocessing), `test_install_cron.sh` (crontab 스텁) | F-23, F-29, F-25, F-26 | High | Done | `feat/kakao-token-scheduled-refresh` |
| T-40 | `.gitignore` 에 `kakao_token.json.lock` 추가 + README 설치·제거·로그 안내 갱신 | — | Mid | Done | `feat/kakao-token-scheduled-refresh` |

### 의존성 그래프

```
T-36 (KakaoAuth 락) ──┐
                      ├── T-37 (refresh entry) ──┐
                      │                           ├── T-39 (테스트)
                      └── T-38 (cron installer) ─┘
                                                  └── T-40 (docs)
```

## museum-finder UI 정렬 (어드민 전면 리디자인)

**PRD:** `docs/prd/20260424_170133_museum-finder-ui-alignment_9952fbc8.md`
**통합 브랜치:** `feat/museum-finder-ui-alignment`
**PR 전략:** 단일 PR (전 태스크 통합 후 1회 머지)

| ID | 설명 | PRD | 우선순위 | 상태 | 브랜치 |
|----|------|-----|----------|------|--------|
| T-41 | 의존성 정리 — `bootstrap`·`bootstrap-icons` 제거, `@playwright/test`·`@axe-core/playwright`·`focus-trap` 추가 | F-22 | High | Done | `feat/museum-finder-ui-alignment` |
| T-42 | 디자인 토큰 이식 — `web/src/styles/tokens.css`·`globals.css` | F-01·F-02 | High | Done | `feat/museum-finder-ui-alignment` |
| T-43 | 공용 `<BaseHead>` 파셜 — NanumSquare/JetBrains Mono CDN + CSP + `font-display: swap` | F-03 | High | Done | `feat/museum-finder-ui-alignment` |
| T-44 | Astro 프리미티브 8종 — Button/Input/Select/Pill/Icon/DataTable/PageHeader/HelpTip + 각 islands | F-04a~h | High | Done | `feat/museum-finder-ui-alignment` |
| T-45 | 레이아웃 셸 — `AppShell`/`Sidebar`(NC 로고)/`Topbar` | F-05·F-06·F-07 | High | Done | `feat/museum-finder-ui-alignment` |
| T-46 | 공용 `Modal.astro` + `islands/modal.ts` (focus-trap, ESC, backdrop) | F-13 | High | Done | `feat/museum-finder-ui-alignment` |
| T-47 | 대시보드 `/admin/index.astro` | F-08 | High | Done | `feat/museum-finder-ui-alignment` |
| T-48 | 처리 이력 목록 `/admin/posts/index.astro` — 필터·검색·페이지네이션·정렬 | F-09 | High | Done | `feat/museum-finder-ui-alignment` |
| T-49 | 게시물 상세 `/admin/posts/[id].astro` — 본문·카톡·재발송(쿨다운 island) | F-10 | High | Done | `feat/museum-finder-ui-alignment` |
| T-50 | 2FA 설정 이동 `/admin/settings/2fa.astro` | F-11 | High | Done | `feat/museum-finder-ui-alignment` |
| T-51 | 로그인·회원가입 리디자인 | F-12 | High | Done | `feat/museum-finder-ui-alignment` |
| T-52 | ErrorLayout 리스타일 + 다크 토큰 이식 | F-17·F-18 | Mid | Done | `feat/museum-finder-ui-alignment` |
| T-53 | 미들웨어 리다이렉트 (`/`→`/admin`, `/settings/2fa`→`/admin/settings/2fa`, 루프 방지) | F-14 | High | Done | `feat/museum-finder-ui-alignment` |
| T-54 | Playwright 인프라 — `playwright.config.ts` + `web/tests/e2e/` | F-19 | High | Done | `feat/museum-finder-ui-alignment` |
| T-55 | axe 통합 + 공용 fixture | F-20 | High | Done | `feat/museum-finder-ui-alignment` |
| T-56 | CI `web` 잡 추가 — astro check/build + playwright install 캐시 + playwright test | F-21 | High | Done | `feat/museum-finder-ui-alignment` |
| T-57 | E2E 시나리오 — 로그인/목록/필터/페이지네이션/상세/재발송/2FA/리다이렉트 | F-15·F-24 | High | Done | `feat/museum-finder-ui-alignment` |
| T-58 | 프리미티브 단위 AC E2E — Select 키보드, HelpTip ESC, Modal 트랩 | F-23 | High | Done | `feat/museum-finder-ui-alignment` |
| T-59 | 육안 검증 체크리스트 `docs/qa/visual-check.md` | F-25 | Mid | Done | `feat/museum-finder-ui-alignment` |
| T-60 | 기존 인라인 스타일 제거 — `pages/index.astro` 등 `<style>` 블록 삭제 + 컴포넌트 호출 대체 | — | High | Done | `feat/museum-finder-ui-alignment` |

### 의존성 그래프

```
T-41 (deps) ─┬── T-42 (tokens) ──┬── T-43 (fonts/head) ──┐
             │                   │                       │
             │                   └── T-44 (primitives) ──┼── T-45 (shell) ──┐
             │                                           │                   │
             │                                           └── T-46 (Modal) ──┤
             │                                                               │
             └── T-54 (playwright) ── T-55 (axe) ── T-56 (CI) ──────────────┤
                                                                             ▼
                                                    T-47~T-52 (pages) ──┬── T-57~T-58 (E2E)
                                                    T-53 (middleware) ──┤
                                                                         │
                                                            T-60 (cleanup)
                                                                         │
                                                            T-59 (육안 체크)
```

## 공지사항 Google Photos 업로드 제거

**PRD:** `docs/prd/20260425_085951_remove-notice-google-photos-upload_a8d4k2p9.md`
**통합 브랜치:** `feat/remove-notice-google-photos-upload`

| ID | 설명 | PRD | 우선순위 | 상태 | 브랜치 |
|----|------|-----|----------|------|--------|
| T-61 | 공지 처리 경로에서 Google Photos import, 클라이언트 생성, 업로드/앨범 추가 호출, 공지 앨범 상수 제거 | F-01, F-02, F-05 | High | Done | `feat/remove-notice-google-photos-upload` |
| T-62 | 공지 이미지 처리 회귀 테스트 추가: 다운로드/분석/카카오/DB 유지 및 Google Photos 의존성 부재 확인 | F-01, F-02, F-03, F-04 | High | Done | `feat/remove-notice-google-photos-upload` |
| T-63 | 공지 개별 게시글 처리 재시도와 최종 실패 `FAIL` DB 기록 구현 | F-06, F-07, F-08 | High | Done | `feat/remove-notice-google-photos-upload` |
| T-64 | 재시도 성공/최종 실패/다음 게시글 계속 처리 테스트 추가 | F-06, F-07, F-08 | High | Done | `feat/remove-notice-google-photos-upload` |

### 의존성 그래프

```
T-61 (업로드 제거) ── T-62 (회귀 테스트)
                    └── T-63 (재시도/FAIL 기록) ── T-64 (실패 경로 테스트)
```
