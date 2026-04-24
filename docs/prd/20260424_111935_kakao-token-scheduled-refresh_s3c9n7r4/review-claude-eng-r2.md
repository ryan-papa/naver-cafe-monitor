# 엔지니어링 리뷰 r2 (Claude)

**판정:** PASS (8.3)

## 채점

| # | 항목 | 점수 | 근거 |
|---|------|------|------|
| 1 | 실현·정합성 | 9 | `src/kakao_refresh.py` + `python -m src.kakao_refresh` 로 `load_config()`·`KakaoAuth` import 성립. r1 P1-A/B 해결 |
| 2 | install_cron.sh 확장 | 8 | 2마커 분리·멱등 재삽입·`--uninstall=<refresh\|batch\|all>` + 잘못된 값 exit 2 구체화 |
| 3 | 동시성(F-29) | 8 | fcntl LOCK_EX + 락 후 재로드→머지→atomic rename. 볼러틸 필드 화이트리스트 명시, rotation refresh_token 유실 방지 |
| 4 | macOS cron 환경 | 9 | venv python 절대경로, `cd $BATCH_DIR`, `load_config()` 저장소 루트 자동 로드, `:15` 시각 분리 |
| 5 | 테스트 가능성 | 8 | crontab 스텁 PATH 주입 + 임시 HOME, 4케이스(refresh/batch/all/foo), threading 락 테스트, 마스킹 검증 명시 |
| 6 | 보안 | 9 | 정규식/JSON 파싱 기반 토큰 마스킹, `.gitignore` 락파일 추가, 상태코드·만료시각만 기록 |

## 잔여 권고 (Non-blocking)

| 항목 | 권고 |
|------|------|
| 마스킹 구현 | `resp.text` 로그 전 JSON 파싱 선행, 파싱 실패 시 정규식 fallback 순서 명시 |
| 락 범위 | `_load_token()` 초기화 읽기도 shared lock 고려(배치 기동 중 refresh 교차) |
| 테스트 이식성 | bash 테스트의 `crontab` 스텁 경로 격리(PATH 선두) 문서화 |

최저 8 → **PASS**. 다음 단계 진입 가능.
