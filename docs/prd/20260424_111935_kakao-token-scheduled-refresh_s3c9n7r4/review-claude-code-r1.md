# 코드 리뷰 r1 — claude-code (서브에이전트, 독립 판정)

**대상:** `feat/kakao-token-scheduled-refresh`
**PRD:** `docs/prd/20260424_111935_kakao-token-scheduled-refresh_s3c9n7r4.md`

## 채점

| # | 항목 | 점수 | 근거 |
|---|------|:---:|------|
| 1 | PRD F-23~F-29 충족 | 9 | 엔트리·락·머지·2엔트리 cron·`--uninstall` 4케이스·마스킹·전용 로그 전부 구현. `_BATCH_ROOT/logs` 경로도 규격 일치 |
| 2 | 에러 처리 | 9 | `load_config`/`__init__`/`refresh` 3단 try, JSON 손상 → `InvalidTokenFile`, 락 실패는 fcntl 예외 자연 전파, cron 설치 실패는 venv/arg 검증 후 exit 1/2 |
| 3 | 보안 (토큰 마스킹) | 9 | `_mask_tokens` JSON+regex 이중, 성공 경로도 토큰 원문 미기록(테스트 검증), `.gitignore` 락파일 추가 |
| 4 | 동시성 | 8 | fcntl LOCK_EX + 재로드·머지 + 화이트리스트 + atomic rename 정상. **주의:** `refresh()` 가 HTTP POST(최대 30s timeout) 전체를 락 내부에서 수행 → 배치 `mark_alert_sent` 최대 30s 블록. 기능적 안전하나 교차지연 가능 |
| 5 | 테스트 커버리지·독립성 | 9 | `multiprocessing.fork` 로 진짜 프로세스간 검증(P1 지연 0.5s, P2 지연 0.1s), 화이트리스트 위반·마스킹 JSON/regex 양 경로·cron 7시나리오(재실행 멱등·4 uninstall·재복구) |
| 6 | 가독성·일관성 | 9 | 모듈 docstring·타입힌트·한글 주석·`_VOLATILE_FIELDS` 상수화·`_commit_changes` 단일 경로 정리. `kakao_refresh.py` 에서 `auth._token_data` private 접근은 사소한 스멜 |
| 7 | 운영 편의성 | 9 | `--uninstall[=..]`·usage·재설치 멱등·로그 안내·부분 롤백 경로 명시. README·tasks.md 연동 |

**최저 = 8 (동시성)** → **PASS (8.0+)**

## 개선 bullet (비차단)

- `KakaoAuth.refresh()`: HTTP POST 를 락 밖에서 수행하고, 성공 후 `_commit_changes()` 로 머지하면 락 점유 시간 단축. 단 "disk 최신 refresh_token 사용" 요구를 유지하려면 락 → 재로드 → 락 해제 → POST → 락 → 재로드·검증 → 머지 2단 구조 필요
- `kakao_refresh.py` 의 `auth._token_data.get("refresh_token_expires_at")` 는 `check_refresh_token_expiry()` 와 중복 — public getter 추가 권장
- `datetime.fromtimestamp(expires_at)` 에 tz 미지정(local) → `_KST` 와 일관되도록 `tz=_KST` 명시 권장
- `install_cron.sh`: `remove_marker` 가 마커 문자열을 포함한 다른 라인도 제거할 여지(현 운영 영향 없음, 방어 차원 `grep -v` 에 라인 끝 앵커 고려)
