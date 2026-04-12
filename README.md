# naver-cafe-monitor

> 세화유치원 네이버 카페 새 게시글 감지 → 얼굴 필터링 → AI 요약 → 카카오톡 알림 자동화 봇

---

## 기능 요약

| 게시판 | 파이프라인 | 대상 필터 |
|--------|-----------|----------|
| 사진게시판 (`menus/13`) | 이미지 전체 다운로드 → 얼굴 인식 필터링 → Google Photos 업로드 → sonnet 요약 → 카카오톡 전송 | 기준 얼굴 매칭 |
| 공지사항 (`menus/6`) | 이미지 2+3등분 병렬 분석 (opus) → 내용/일정 분리 전송 | 7세 또는 전체 대상만 |

---

## 아키텍처 플로우

```
[cron 30분] → start.sh → batch.py
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
         사진게시판(13)            공지사항(6)
                │                       │
      Playwright 크롤링          Playwright 크롤링
                │                       │
      이미지 다운로드            이미지 분할 캡처
                │                       │
      DeepFace 얼굴 필터      Claude CLI opus 분석
                │                  (2+3등분 병렬)
      Google Photos 업로드          │
                │              대상 필터링
      Claude CLI sonnet 요약    (7세/전체)
                │                       │
                └───────────┬───────────┘
                            ▼
                    카카오톡 메시지 발송
```

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| Language | Python 3.11+ |
| Browser | Playwright (headless Chromium) |
| Face Recognition | DeepFace + dlib |
| AI | Claude Code CLI (opus/sonnet) — API 키 불필요 |
| HTTP | httpx |
| Storage | Google Photos API (OAuth) |
| Messaging | 카카오톡 REST API |
| Auth | 네이버 쿠키 기반 세션 |

---

## 전제조건

- Python 3.11+ (`python3.11 --version`)
- cmake (`cmake --version`) — dlib 빌드에 필수
- Playwright chromium
- Claude Code CLI 설치 완료

### macOS

```bash
brew install cmake python@3.11
```

### Linux (Ubuntu/Debian)

```bash
apt-get install -y cmake python3-dev
```

---

## 설치 및 실행

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env
cp config/config.example.yaml config/config.yaml
```

얼굴 기준 이미지 등록:

```bash
python -m src.face.cli register data/faces/reference/photo.jpg --label "이름"
```

수동 실행:

```bash
python -m src.batch
```

---

## 환경변수 (`.env`)

| 변수명 | 설명 |
|--------|------|
| `NAVER_ID` | 네이버 로그인 ID |
| `NAVER_PW` | 네이버 로그인 PW |
| `KAKAO_TOKEN` | 카카오 REST API 토큰 |
| `ANTHROPIC_API_KEY` | (미사용 — CLI 기반) |
| `CONFIG_PATH` | 설정 파일 경로 (기본: `config/config.yaml`) |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

---

## 설정 (`config/config.yaml`)

| 섹션 | 주요 항목 |
|------|----------|
| `cafe` | 카페 ID, 게시판 목록 (`menus/13`, `menus/6`) |
| `face` | 유사도 임계값 (`tolerance: 0.55`), 기준 이미지 경로 |
| `notification` | 카카오 수신자 (본인, 배우자) |
| `summary` | AI 모델, 최대 토큰 |
| `retry` | 재시도 횟수, 지수 백오프 |

---

## 배치 실행 (cron)

```bash
bash scripts/install_cron.sh
```

수동 등록 시:

```bash
crontab -e
# */30 * * * * cd /path/to/naver-cafe-monitor && bash scripts/start.sh >> logs/cron.log 2>&1
```

---

## 수동 로그인 절차

네이버 카페는 쿠키 기반 인증을 사용한다. 쿠키 만료 시:

1. `python -m src.crawler.login` 실행
2. Playwright 브라우저가 열리면 네이버 수동 로그인
3. 로그인 완료 후 쿠키가 자동 저장됨

---

## 프로젝트 구조

```
src/
├── batch.py            # 배치 진입점
├── config.py           # 설정 로더
├── crawler/
│   ├── login.py        # 네이버 로그인·쿠키 관리
│   ├── naver_cafe.py   # 카페 크롤러
│   ├── parser.py       # 게시글 파싱
│   ├── image_downloader.py
│   ├── post_tracker.py # 중복 게시글 추적
│   ├── session.py      # 세션 관리
│   └── urls.py         # URL 상수
├── face/
│   ├── cli.py          # 얼굴 등록 CLI
│   ├── encoder.py      # 얼굴 인코딩
│   └── filter.py       # 얼굴 매칭 필터
├── messaging/
│   └── kakao.py        # 카카오톡 발송
├── notice/
│   ├── extractor.py    # 공지 텍스트 추출
│   └── summarizer.py   # AI 요약
├── scheduler/          # 스케줄러
└── storage/
    └── google_photos.py # Google Photos 업로드
scripts/
├── start.sh            # 배치 실행
└── install_cron.sh     # cron 등록
config/
└── config.example.yaml
tests/                  # 단위 테스트
```
