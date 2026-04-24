# PRD: 카카오 토큰 주기 선제 갱신 (3시간 cron)

**ID:** 20260424_111935_kakao-token-scheduled-refresh_s3c9n7r4
**날짜:** 2026-04-24
**상태:** Draft
**선행 PRD:** [20260413_202128_kakao-token-auto-refresh_k7m3x9p2](./20260413_202128_kakao-token-auto-refresh_k7m3x9p2.md)

---

## 개요·목적

- **배경:** 선행 PRD로 `KakaoAuth.refresh()` 401 자동 갱신은 구현됨. 그러나 access token(6h 수명)이 30분 배치 실행 시점에만 갱신되어 매 갱신 사이클에서 최소 1회 401이 발생함. 또한 refresh token(60일 수명)은 Kakao rotation 정책상 만료 30일 이내 갱신 호출에서만 연장되므로, 배치 401 경로에만 의존하면 rotation 누락 위험 존재
- **목표:** OS 레벨 cron으로 3시간 주기 선제 refresh 실행 → access token 상시 pre-warm + refresh token 무기한 rotation 연장
- **범위:** 신규 `kakao_refresh.py` 스크립트, `install_cron.sh` 확장(2-entry + `--uninstall` 옵션), 전용 로그 파일

## 사용자 스토리

| As a | I want | So that |
|------|--------|---------|
| 운영자 | 배치와 별도 cron으로 3시간마다 토큰을 선제 갱신하길 | 배치 실행 시 401 실패·재시도 경로를 최소화한다 |
| 운영자 | refresh/batch cron을 개별적으로 제거하길 | 장애 시 refresh만 빠르게 중단하고 배치는 유지할 수 있다 |
| 운영자 | refresh 로그가 배치 로그와 분리되길 | 장애 추적·분석이 용이하다 |

## 기능 요구사항

| ID | 요구사항 | 우선순위 | AC (완료 조건) |
|----|----------|----------|---------------|
| F-23 | **신규 모듈 `batch/src/kakao_refresh.py`** (scripts/ 아님 — `src` 패키지 import 성립 위해 src 하위에 배치). `load_config()`로 `.env` 로드 → `KakaoAuth` 생성 → `refresh()` 호출. 성공 INFO 로그(만료시각, 남은 일수), 실패 ERROR 로그(상태코드 + **마스킹된 응답본문**), exit code 0/1. cron 실행 커맨드: `cd $BATCH_DIR && $VENV_DIR/bin/python -m src.kakao_refresh` | High | mock API에서 성공/401/네트워크에러 → 로그·exit code 검증 + `.env` 누락 시 명확한 에러 |
| F-24 | `batch/logs/kakao_refresh.log` 전용 로그 파일. Python `logging` + `FileHandler`. **로그 본문에서 토큰 값 마스킹 필수**: 응답 JSON의 `access_token`/`refresh_token` 값은 `***`로 치환(정규식 또는 JSON 파싱 후 필드 제거) | High | mock 응답에 토큰 문자열 포함 → 로그 파일에 원본 토큰 문자열 미출력 검증 |
| F-25 | `install_cron.sh` 확장: batch 엔트리(`*/30 * * * *`) + refresh 엔트리(`15 */3 * * *`). 마커 `# naver-cafe-monitor batch` / `# naver-cafe-monitor kakao-refresh` 분리. **멱등성**: 재실행 시 각 마커의 기존 라인을 제거 후 재삽입(중복 방지) | High | 2회 연속 실행 시 `crontab -l` 각 마커 정확히 1줄씩 유지 |
| F-26 | `install_cron.sh --uninstall=<refresh\|batch\|all>` 옵션. 미지정 시 기본값 `all`. **잘못된 값(`--uninstall=foo`)은 usage 에러 + exit 2**. 제거 순서는 마커 grep 필터링 후 `crontab -` 로 원자적 교체 | High | `refresh`/`batch`/`all`/`foo` 4케이스 검증 (정상 3개 + 에러 1개) |
| F-27 | refresh 실패 시 ERROR 로그만 기록, 다음 주기(3h 후) 자연 재시도. 즉시 알림 없음. **최종 안전망:** 선행 PRD F-17/F-18의 만료 14일 전 경고가 rotation 누락 최악 시나리오를 포착 | Mid | 실패 mock 실행 시 알림 전송 호출 없음 + ERROR 로그만 기록 검증 |
| F-28 | `KakaoMessenger`의 401 자동 갱신 로직 유지(삭제 금지). 기존 테스트 회귀 통과 | High | 기존 `test_kakao_auth.py`·`test_messaging.py` 회귀 통과 |
| F-29 | **`KakaoAuth` 파일 락 보강**: `_save_token()` 및 read-modify-write 경로(`refresh()`, `mark_alert_sent()`)에서 sidecar 락파일(`kakao_token.json.lock`)에 `fcntl.flock(LOCK_EX)` 획득. 락 획득 후 파일 재로드 → 메모리 `_token_data`와 머지(볼러틸 필드만 덮어쓰기: `access_token`, `expires_at`, 필요 시 `refresh_token`/`refresh_token_expires_at`, `last_alert_date`) → atomic rename → 락 해제. refresh cron과 batch 배치가 **서로 다른 프로세스**로 교차 실행돼도 rotation된 refresh_token 유실 방지 | High | **프로세스 간 테스트 필수**(threading 검증은 부적합): `multiprocessing.Process` 또는 `subprocess` 로 독립 프로세스 2개 생성, 한쪽은 cron refresh(회전된 refresh_token 쓰기), 다른쪽은 batch `mark_alert_sent()` 실행. 두 프로세스가 인위적 지연으로 락 경합을 유도한 뒤, 최종 파일에 회전된 refresh_token과 `last_alert_date` 가 **둘 다** 보존되는지 검증 |

## 비기능 요구사항

| 항목 | 요구사항 |
|------|----------|
| 하위 호환 | 기존 `install_cron.sh` 무인자 실행 결과 유지(batch + refresh 둘 다 설치). 운영자 재학습 최소 |
| 동시성 | 시각 분리(`:15` vs `:00/:30`) + atomic rename + **fcntl 파일 락(F-29)** 3중 방어. 시각 분리는 통상 회피, 락은 최악 경우 방어 |
| 관측가능성 | 로그 형식: `YYYY-MM-DD HH:MM:SS KST - LEVEL - message`. 성공 INFO, 실패 ERROR. 실패 응답 body는 토큰 값 마스킹 후 기록 |
| 안정성 | refresh 실패는 배치 운영에 영향 없음(401 재시도 경로 유지). 3회 연속 실패여도 수동 개입 전까지 배치는 계속 동작 |
| 보안 | 로그에 access_token/refresh_token 원문 금지 (F-24 마스킹). 만료시각·상태코드만 기록. 토큰 파일·락파일 `.gitignore` 포함 |
| 실행 환경 | cron 커맨드: `cd $BATCH_DIR && $VENV_DIR/bin/python -m src.kakao_refresh >> $LOG_FILE 2>&1`. macOS cron의 제한 PATH 환경 고려해 venv python **절대경로** 사용, `.env`는 `load_config()` 가 저장소 루트에서 자동 로드 |

## 테스트 전략

| 레벨 | 대상 | 방법 |
|------|------|------|
| 단위 | `src.kakao_refresh` entry point | mock `KakaoAuth.refresh()` → 성공/실패 분기, exit code, 로그 메시지·토큰 마스킹 검증 |
| 단위·프로세스간 | `KakaoAuth` 파일 락 (F-29) | `multiprocessing.Process` 또는 `subprocess` 로 **독립 프로세스 2개** 동시 기동 → refresh(P1: 토큰 회전) + mark_alert_sent(P2: last_alert_date) 교차 수행. 최종 토큰 파일에 두 변경 모두 보존 검증. threading 기반 검증은 금지(프로세스 간 `fcntl.flock` 동작 재현 불가) |
| 단위 | `install_cron.sh` | `crontab` 을 PATH 앞단에 스텁으로 두고 임시 HOME에서 bash 테스트: 재설치 멱등, `--uninstall=refresh\|batch\|all\|foo` 4케이스 검증 |
| 회귀 | 기존 `KakaoAuth`·`KakaoMessenger` | 기존 테스트 전량 통과 (F-29 변경이 기존 동작 깨뜨리지 않는지) |
| 수동 검증 | 실제 cron 등록 후 1주기(3h) 관찰 | 로그 파일 생성·INFO 메시지·토큰 파일 mtime 갱신 확인 |

## 연쇄 변경 대상

| 파일 | 변경 내용 |
|------|----------|
| `batch/src/kakao_refresh.py` | **신규**. `python -m src.kakao_refresh` 엔트리. `load_config()` → `KakaoAuth(...).refresh()` → 로깅(마스킹) → exit code |
| `batch/src/messaging/kakao_auth.py` | F-29 반영: fcntl 파일 락 컨텍스트 매니저 추가, `_save_token`·`refresh`·`mark_alert_sent` 가 락 획득 + 재로드·머지 수행 |
| `batch/scripts/install_cron.sh` | refresh 엔트리(`python -m src.kakao_refresh`) 추가, 마커 분리, `--uninstall=<refresh\|batch\|all>` 파싱, 재실행 멱등성 |
| `batch/tests/test_kakao_refresh.py` | **신규**. entry point + 마스킹 단위 테스트 |
| `batch/tests/test_kakao_auth_lock.py` | **신규**. F-29 락·머지 동시성 단위 테스트 |
| `batch/tests/test_install_cron.sh` | **신규**. `crontab` 스텁 기반 bash 테스트 |
| `.gitignore` | `batch/config/kakao_token.json.lock` 추가 |
| `README.md` | refresh cron 설치·제거·로그 위치 안내 |

## 제약사항

- 기술: macOS cron의 PATH 한정 환경 → venv python 절대경로 필수
- 기술: Kakao refresh token rotation은 만료 30일 이내 갱신 호출에서만 발생 → 3시간 주기는 rotation 트리거 충분히 커버
- 운영: cron 등록은 서버(Mac Mini) 로컬에서 수동 실행(`bash batch/scripts/install_cron.sh`). 자동 배포에 포함하지 않음(cron 권한·환경 차이 리스크)

## 마이그레이션·롤백

- **적용:** 서버에서 `bash batch/scripts/install_cron.sh` 재실행 → batch+refresh 양쪽 설치
- **부분 롤백:** `bash batch/scripts/install_cron.sh --uninstall=refresh` → refresh만 제거, 배치는 유지. 선행 PRD의 401 자동 갱신이 fallback으로 동작
- **전체 롤백:** `--uninstall=all` → 모든 엔트리 제거
- **영향 범위:** refresh 제거 시에도 배치·API 운영 무영향 (선행 PRD 안전망)

## 수용 리스크

- refresh cron이 장시간 조용히 실패할 경우, 실제 운영자 신호는 선행 PRD F-17의 "만료 14일 전 경고"가 발송되는 시점까지 지연될 수 있음. cron 주기(3h) 대비 14일은 충분한 버퍼이며, 즉시 알림 도입은 범위 확장으로 판단해 **수용**

## Out of Scope

- refresh 실패 즉시 알림 / 연속 N회 실패 임계 알림 (상기 수용 리스크 항목 참조)
- launchd 이관 (현 cron 운영 일관성 유지)
- GitHub Actions scheduled workflow (로컬 토큰 파일 접근 불가)
