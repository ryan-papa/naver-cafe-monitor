# PRD — 배치 기본 경로를 repo 루트 기준으로 통일 (Lite)

| 항목 | 내용 |
|------|------|
| 트랙 | Lite (핫픽스) |
| 범위 | `batch/src/config.py`, `batch/src/storage/google_photos.py`, `batch/src/messaging/kakao_auth.py`, `batch/src/crawler/session.py` |
| 영향 | 상위 디렉토리 rename·cwd 변경 시 배치 전량 실패 |

## 배경
batch 모듈 기본 경로가 `batch/config/*`, `batch/data/cookies.json` (또는 cwd 기준 상대경로)으로 정의되어 있었고, 실제 파일은 repo 루트 `config/`·`data/`에 있어서 `batch/config/*`는 절대경로 심볼릭 링크로 연결된 상태였음. `claude-projects → workflow-agent-harness` 디렉토리 rename으로 심볼릭 링크가 전부 dead link가 되어 오늘 14:00~18:30 cron 실행 전량 `FileNotFoundError`.

## 목표
심볼릭 링크 의존 제거. 모든 모듈이 `__file__` 기준으로 repo 루트를 계산해 `config/`·`data/`를 직접 참조.

## In
- `batch/src/config.py` : `_CONFIG_DIR = _REPO_ROOT / "config"`
- `batch/src/storage/google_photos.py`, `batch/src/messaging/kakao_auth.py` : `_REPO_ROOT = parents[3]`, 토큰 경로 repo 루트 기준
- `batch/src/crawler/session.py` : `_DEFAULT_COOKIE_PATH = _REPO_ROOT / "data" / "cookies.json"` (기존 cwd 의존 상대경로)
- 회귀 테스트 `batch/tests/test_default_paths.py` 4 case

## Out
- `batch/config/`·`batch/data/` 심볼릭 링크 제거 (gitignored, 로컬 잔존 무해)
- 실파일 위치 이동
- Docker 이미지 내부 경로 재정의

## 테스트
- `pytest batch/tests/test_default_paths.py` — 4 passed
- 전체 스위트 408 passed
- 로컬 `python -m src.batch` E2E: DB → 쿠키 25개 → 크롤 → 완료
