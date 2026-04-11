# naver-cafe-monitor

네이버 카페 게시판 모니터링 도구. 새 게시글 감지 → 얼굴 인식 필터링 → AI 요약 → 카카오 알림 발송.

## 요구사항

- Python 3.11+
- Docker (선택)

## 설치

```bash
# 1. 의존성 설치
pip install -e ".[dev]"

# 2. Playwright 브라우저 설치
playwright install chromium

# 3. 환경변수 설정
cp .env.example .env
# .env 파일에 값 입력

# 4. 설정 파일 복사
cp config/config.example.yaml config/config.yaml
# config/config.yaml 편집
```

## 실행

```bash
# 직접 실행
python -m src.scheduler

# Docker
docker build -t naver-cafe-monitor .
docker run --env-file .env -v $(pwd)/config:/app/config naver-cafe-monitor
```

## 테스트

```bash
pytest
pytest --cov=src
```

## 구조

- [`src/crawler/`](src/crawler/) — Playwright 기반 크롤러
- [`src/face/`](src/face/) — 얼굴 인식 (face_recognition)
- [`src/notice/`](src/notice/) — 게시글 감지 및 중복 필터
- [`src/messaging/`](src/messaging/) — 카카오 메시지 발송
- [`src/scheduler/`](src/scheduler/) — APScheduler 진입점
- [`config/config.example.yaml`](config/config.example.yaml) — 설정 예시
- [`Dockerfile`](Dockerfile) — 컨테이너 빌드
