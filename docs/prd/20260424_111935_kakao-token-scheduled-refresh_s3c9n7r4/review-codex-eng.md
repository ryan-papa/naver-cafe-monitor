# Codex 엔지니어링 리뷰 결과

**대상:** `docs/prd/20260424_111935_kakao-token-scheduled-refresh_s3c9n7r4.md`
**실행:** `codex review` (foreground, 1회)
**일시:** 2026-04-24

## 지적 사항 (P1 × 3)

### [P1-A] `batch/scripts/` 위치로는 `src` import 깨짐
- `src.messaging.kakao_auth`·`src.config` import 불가. 기존 배치가 cron에서 동작하는 이유는 `python -m src.batch` 패턴을 사용하기 때문.

### [P1-B] .env 로딩 누락
- `KakaoAuth`는 `client_id`/`client_secret`을 인자로만 받음. cron 환경은 PATH·env 거의 없음. `load_config()`/`load_dotenv()` 기반 env bootstrap 필요.

### [P1-C] atomic rename 만으로 토큰 경합 방지 불충분
- `KakaoAuth._save_token()`이 메모리 전체를 덮어씀. refresh cron이 새 `refresh_token`으로 저장 후, 이미 로드된 배치 프로세스가 `mark_alert_sent()`·자체 `refresh()` 수행 시 오래된 `_token_data`로 덮어써 회전된 토큰 유실 가능.

## Claude 엔지니어링 리뷰 보조 지적 (r1 FAIL 7.0)

- S1: 실패 응답 본문 토큰 마스킹 규칙 부재
- S2: `--uninstall` 유효성 검증 및 재설치 멱등성 AC 부재
- S3: `crontab` 스텁 기반 bash 테스트 방법 미구체화

## 반영

| 지적 | 해결 방법 |
|------|----------|
| P1-A | `batch/src/kakao_refresh.py` 로 위치 이동, `python -m src.kakao_refresh` 실행 |
| P1-B | `load_config()` 호출로 `.env` 자동 로드 명시 (F-23) |
| P1-C | F-29 신규: `fcntl.flock(LOCK_EX)` + 락 획득 후 재로드·머지 패턴. `_save_token`·`refresh`·`mark_alert_sent` 적용 |
| S1 | F-24: 토큰 값 정규식/JSON 마스킹 필수 명시 |
| S2 | F-25 멱등성 AC, F-26 `foo` 케이스 usage 에러 + exit 2 |
| S3 | 테스트 전략: `crontab` PATH 스텁 + 임시 HOME 기반 bash 테스트 명시 |

## 결론

High 3건 + 보조 3건 모두 반영. 다음 단계(엔지니어링 리뷰 r2) 진입.
