# 엔지니어링 리뷰 r1 (Claude 서브에이전트)

**대상:** `20260424_111935_kakao-token-scheduled-refresh_s3c9n7r4.md`
**리뷰어:** Claude 서브에이전트 (독립·메인 컨텍스트 없음)

## 항목별 채점

| # | 항목 | 점수 | 근거 |
|---|------|-----:|------|
| 1 | 구현 실현 가능성 / `KakaoAuth` 정합성 | 9 | `KakaoAuth.refresh()`가 이미 토큰 파일 갱신·atomic write·만료 필드 재계산까지 처리. 신규 스크립트는 단순 엔트리포인트로 재사용 가능. `.env` 로드 경로만 `kakao_setup.py`와 동일하게 유지하면 됨 |
| 2 | `install_cron.sh` 확장 설계 | 8 | 마커 2종 분리·`--uninstall=refresh\|batch\|all` 명시, 기존 `grep -v` 제거 로직 확장 가능. 다만 `--uninstall` 인자 유효성 검증·알 수 없는 값 거부·재설치 시 양쪽 마커 제거 후 재삽입 전략이 PRD 본문에는 미기재 (테스트 케이스로만 암시) |
| 3 | 동시성·경합 | 9 | batch `:00/:30` vs refresh `:15` 시각 분리 + `KakaoAuth._save_token()` atomic rename(tempfile→replace) 확인됨. 실질 경합 확률 낮음 |
| 4 | macOS cron 특수성 | 9 | 비기능 요구사항에 venv 절대경로·cwd 이동·PATH 제한 명시. 기존 `install_cron.sh`가 이미 절대경로 패턴 사용 중이라 확장 자연스러움 |
| 5 | 테스트 가능성 | 8 | Python entry point mock 테스트·bats/shell 테스트 전략 기재. 다만 `crontab` mock 주입 방법(예: `PATH` 앞단 스텁 바이너리)이 구체화되지 않음 |
| 6 | 보안·비밀 누출 | 7 | "토큰 값 기록 금지, 만료시각·상태코드만" 명시. 그러나 F-23 AC는 "실패 시 응답 본문 ERROR 로그"로 되어 있고 기존 `KakaoAuth.refresh()`도 `resp.text` 전체를 로깅함 — 실패 응답 본문에 민감 정보(refresh_token 에코 등)가 포함될 수 있어 필드 필터링 가이드 부재 |

## 판정

- **최저 점수:** 7 (보안·비밀 누출)
- **평균:** 8.33
- **판정:** FAIL (최저 7 < 8.0)

## 개선 요구 항목

| ID | 개선 내용 |
|----|----------|
| S1 | F-23/비기능 보안에 "실패 응답 본문 로깅 시 `access_token`·`refresh_token` 키 마스킹/필터링" 명시. 기존 `kakao_auth.py:110-115`의 `resp.text` 원문 로깅도 동일 가드 적용 범위 포함 |
| S2 | F-26 AC에 "알 수 없는 `--uninstall` 값은 비영점 exit + usage 출력" 추가, 재설치 시 기존 두 마커 모두 제거 후 원자적 재삽입 순서 명시 |
| S3 | 테스트 전략에 `crontab` 스텁 주입 방식(예: 임시 PATH 스텁, HOME 격리) 구체 기술 |

개선 반영 후 r2 재리뷰 권장.
