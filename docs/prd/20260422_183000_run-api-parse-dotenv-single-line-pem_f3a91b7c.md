# PRD — run_api.parse_dotenv: single-line PEM 처리 (Lite)

| 항목 | 내용 |
|------|------|
| 트랙 | Lite (핫픽스) |
| 범위 | `scripts/deploy/run_api.py` 1파일, 1줄 |
| 영향 | API 기동 시 AUTH 관련 env 누락 → `/api/auth/public-key` 500 |

## 배경
sops 디코드된 `.env.enc`에서 PEM 값이 단일 라인 + 리터럴 `\n`으로 인코딩됨. 기존 `parse_dotenv`는 `-----BEGIN ` 감지 시 multi-line 모드로 전환 후 `-----END ...-----`로 끝나는 라인까지 누적 → 같은 라인에 END 마커가 있으면 파서가 빠져나오지 못하고 이후 키들을 값에 흡수.

## 목표
`AUTH_RSA_PRIVATE_KEY`, `AUTH_RSA_PUBLIC_KEY`, `AUTH_AES_KEY`, `AUTH_HMAC_KEY`, `AUTH_JWT_SECRET` 모두 환경변수로 정상 주입.

## In
- `parse_dotenv`가 단일 라인 PEM(`BEGIN`과 `END`가 같은 라인)을 값 전체로 저장
- 기존 multi-line PEM 포맷 호환 유지
- `scripts/deploy/tests/test_run_api.py` 유닛 테스트 추가

## Out
- `.env.enc` 재암호화·포맷 변경
- 다른 env 파서 유틸 도입

## 테스트
- `pytest scripts/deploy/tests/` — 2 cases (single-line / multi-line)
- 로컬 수동: `curl http://127.0.0.1:8000/api/auth/public-key` → 200 + PEM 반환
