# naver-cafe-monitor

> 세화유치원 네이버 카페 모니터링 시스템 — 배치 크롤링 + REST API + 웹 대시보드

---

## 기능 요약

| 컴포넌트 | 역할 |
|----------|------|
| **Batch** | 30분 주기 크롤링 → 얼굴 필터링 → AI 요약 → 카카오톡 알림 |
| **API** | 처리 이력 조회 REST API (FastAPI/Uvicorn) |
| **Web** | 처리 이력 대시보드 — 통계, 필터, 페이지네이션, 상세 모달(카카오 전송 내용 미리보기·재발송) (Astro) |

### 배치 파이프라인

| 게시판 | 파이프라인 | 대상 필터 |
|--------|-----------|----------|
| 사진게시판 (`menus/13`) | 이미지 다운로드 → 얼굴 인식 필터링 → Google Photos 업로드 → sonnet 요약 → 카카오톡 전송 | 기준 얼굴 매칭 |
| 공지사항 (`menus/6`) | 이미지 2+3등분 병렬 분석 (opus) → 내용/일정 분리 전송 | 7세 또는 전체 대상만 |

---

## 아키텍처

```
                        ┌─────────────────────────────────┐
                        │         eepp.shop (Mac Mini)     │
                        │                                  │
  브라우저 ──mTLS──→   nginx (443)                         │
                        │  ├─ /naver-cafe-monitoring/api/* ─→ uvicorn (8000) ─→ MySQL
                        │  └─ /naver-cafe-monitoring/*     ─→ static files
                        │                                  │
  [cron 30분] ────→   batch.py                             │
                        │                                  │
            ┌───────────┴───────────┐                      │
            ▼                       ▼                      │
     사진게시판(13)            공지사항(6)                  │
            │                       │                      │
   Playwright 크롤링       Playwright 크롤링               │
            │                       │                      │
   DeepFace 얼굴 필터    Claude opus 분석                  │
            │               (2+3등분 병렬)                 │
   Google Photos 업로드         │                          │
            │             대상 필터링(7세/전체)             │
   Claude sonnet 요약           │                          │
            │                   │                          │
            └───────┬───────────┘                          │
                    ▼                                      │
           카카오톡 메시지 발송                             │
                    │                                      │
                    └──→ MySQL (처리 이력 저장)             │
                        └─────────────────────────────────┘
```

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Frontend | Astro, TypeScript |
| Database | MySQL 8.0 (SSL/X509) |
| Reverse Proxy | nginx (TLS + mTLS) |
| Browser Automation | Playwright (headless Chromium) |
| Face Recognition | DeepFace + dlib |
| AI | Claude Code CLI (opus/sonnet) |
| Storage | Google Photos API (OAuth) |
| Messaging | 카카오톡 REST API |
| Infra | macOS launchd, brew services |

---

## 전제조건

- Python 3.11+
- cmake — dlib 빌드에 필수
- Playwright chromium
- Claude Code CLI

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
| `MYSQL_PASSWORD` | MySQL 접속 비밀번호 |
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

## 배포 (macOS 네이티브)

Mac Mini (`eepp.shop`)에서 Docker 없이 brew + launchd로 운영한다.

### 서비스 구성

| 서비스 | 실행 방식 | 포트 | 관리 |
|--------|-----------|------|------|
| MySQL 8.0 | `brew services` | 3306 | `brew services restart mysql@8.0` |
| nginx | launchd (`dev.eepp.nginx`) | 80, 443 | `sudo launchctl stop dev.eepp.nginx` |
| API (uvicorn) | launchd (`dev.eepp.naver-cafe-monitor-api`) | 8000 | `launchctl stop dev.eepp.naver-cafe-monitor-api` |
| Web (static) | nginx에서 직접 서빙 | — | `/opt/homebrew/var/www/naver-cafe-monitoring/` |

### SSL/mTLS

- nginx: TLS 종단 + 클라이언트 인증서 검증 (mTLS)
- MySQL: `require_secure_transport=ON`, X509 클라이언트 인증

### 라우팅

```
https://eepp.shop/naver-cafe-monitoring/api/*  → 127.0.0.1:8000/api/*  (uvicorn)
https://eepp.shop/naver-cafe-monitoring/*      → static files           (nginx)
http://*                                       → 301 → https
```

### Web 빌드 & 배포

```bash
cd web && npm ci && PUBLIC_API_URL=/naver-cafe-monitoring npm run build
sudo cp -r dist/* /opt/homebrew/var/www/naver-cafe-monitoring/
sudo nginx -s reload
```

---

## 프로젝트 구조

```
naver-cafe-monitor/
├── api/                    # FastAPI 백엔드
│   ├── src/main.py         # API 진입점 (uvicorn)
│   ├── requirements.txt
│   └── tests/
├── batch/                  # 배치 크롤러
│   ├── src/
│   │   ├── batch.py        # 배치 진입점
│   │   ├── config.py       # 설정 로더
│   │   ├── crawler/        # 네이버 크롤링 (login, parser, session)
│   │   ├── face/           # 얼굴 인식 (DeepFace, cli, filter)
│   │   ├── messaging/      # 카카오톡 발송
│   │   ├── notice/         # 공지 추출·요약
│   │   ├── scheduler/      # 스케줄러 (pipeline, poller, retry)
│   │   └── storage/        # Google Photos 업로드
│   ├── scripts/            # start.sh, install_cron.sh
│   ├── config/             # config.example.yaml
│   └── tests/
├── web/                    # Astro 프론트엔드
│   ├── src/pages/
│   ├── astro.config.mjs
│   └── package.json
├── shared/                 # API·배치 공통 모듈
│   ├── database.py         # MySQL SSL 연결
│   ├── post_repository.py  # DB 쿼리
│   └── kakao_format.py     # 카카오톡 메시지 재구성 (API·batch 공용)
├── deploy/                 # 배포 설정 참고용
│   ├── docker-compose.yaml
│   ├── nginx-conf/
│   └── db-init/
├── db/                     # DDL, 마이그레이션
├── docs/prd/               # PRD 문서
└── .github/workflows/      # CI (PR 체크)
```
