# naver-cafe-monitor

네이버 카페 게시판 모니터링 봇. 새 게시글 감지 → 얼굴 인식 필터링 → AI 요약 → 카카오 알림 발송.

## 주요 기능

- 네이버 카페 게시판 자동 크롤링 (Playwright headless)
- 게시글 이미지 내 얼굴 인식 및 기준 이미지 비교 필터링
- 공지사항 텍스트 AI 요약 (일정 정보 포함)
- 카카오톡 메시지 자동 발송
- APScheduler 기반 폴링 (주기 설정 가능)
- 크롤링 실패 시 재시도 (3회/5초 간격)

## 요구사항

- Python 3.11+
- Docker (선택)

### 시스템 의존성 (macOS)

```bash
brew install cmake python@3.11
```

> `dlib` (얼굴 인식 엔진) 빌드에 cmake 필수. 시스템 Python 3.9에서는 빌드 실패 — Python 3.11+ 사용.

### Linux (Ubuntu/Debian)

```bash
apt-get install -y cmake python3-dev
```

## 설치 및 실행

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env          # 환경변수 설정
cp config/config.example.yaml config/config.yaml  # 설정 편집
```

### 얼굴 기준 이미지 등록

```bash
# data/faces/reference/ 에 자녀 정면 사진 3~5장 준비 후:
python -m src.face.cli register data/faces/reference/photo.jpg --label "이름"
```

```bash
# 직접 실행
python -m src.scheduler

# Docker
docker build -t naver-cafe-monitor .
docker run --env-file .env -v $(pwd)/config:/app/config naver-cafe-monitor
```

## 설정

| 파일 | 용도 |
|------|------|
| [`.env.example`](.env.example) | 네이버/카카오/AI API 인증 정보 |
| [`config/config.example.yaml`](config/config.example.yaml) | 카페 ID, 게시판, 폴링 주기, 재시도 등 |

## 테스트

```bash
pytest
pytest --cov=src
```

## 프로젝트 구조

```
src/
├── crawler/        # Playwright 기반 크롤러, 이미지 다운로더, 게시글 추적
├── face/           # 얼굴 인식 및 기준 이미지 등록 CLI
├── notice/         # 공지사항 텍스트 추출 및 AI 요약
├── messaging/      # 카카오 메시지 발송
├── scheduler/      # APScheduler 폴링, 파이프라인, 재시도
└── config.py       # 설정 로더
config/
└── config.example.yaml
tests/              # 모듈별 단위 테스트
docs/prd/           # 제품 요구사항 문서
Dockerfile          # 컨테이너 빌드
```
