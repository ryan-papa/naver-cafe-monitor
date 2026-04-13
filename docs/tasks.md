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
