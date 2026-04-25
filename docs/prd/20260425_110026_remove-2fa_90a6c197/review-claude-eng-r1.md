# PRD 엔지니어링 리뷰 r1

## 점수표
| 항목 | 점수 | 근거 |
|------|------|------|
| 요구사항 명확성 | 9.0 | F-01~F-16 까지 구현 단위로 분해 가능. F-15(기존 토큰 클레임 무시) 호환성까지 명시. F-16 운영자 수동 합격 체크리스트로 검증 절차 구체화 |
| 기술적 실현가능성 | 8.5 | `verify_totp` 제거·`LoginContext.internal` 제거·토큰 클레임 제거·DB DROP 모두 실제 코드와 1:1 매칭. `IF EXISTS` idempotent 처리 명시. 다만 `dependencies.py` 의 부속 헬퍼 정리는 일반화 표현만 존재 |
| 범위·공수 | 8.0 | 누락 파일 3건 존재 (아래 별도 섹션). 공수 M 추정은 합리적 |
| NFR | 7.5 | 외부 차단 우회 시 모니터링 지표 부재, 가용성·관측성(`auth_events` totp 이벤트 신규 발행 차단 검증) NFR 미흡 |
| 의존성·리스크 | 8.5 | `pyotp` 제거, DB 컬럼 DROP, 토큰 클레임 제거(F-15 호환성), `host_classifier` 제거, 단일 관리자 가정, 외부 차단 정책 변경 리스크 모두 식별 |
| 테스트 가능성 | 8.0 | 단위·E2E·idempotent·grep 모두 검증 가능. 다만 F-15 호환성 검증 테스트 케이스 명시 부재. axe 미언급 |

## 평균 / 최저
- 평균: 8.25
- 최저: 7.5 (NFR)

## 합격 여부
PASS

## 강점
- 외부 차단 결정 → dead code 제거 인과 사슬 일관성
- F-15 (기존 토큰 클레임 무시) 호환성 별도 요구사항화
- A/B/C/D 대안 비교 균형
- 영향 파일 표 영역별 분리로 태스크 분해 즉시 가능
- 실패 모드 테이블 코드경로 매핑

## 약점·개선 제안
1. `shared/tests/test_host_classifier.py` 삭제 미명시
2. `api/requirements.txt` 의 `pyotp` 정리 누락
3. `shared/auth_tokens.py` (F-11/F-15 직결) 누락
4. `dependencies.py` 의 `SETUP_ALLOWED_PREFIXES`·`_is_setup_allowed_path` 정리 명시 부족
5. `login_service.py` `__all__`·docstring 정리 명시 부재
6. F-15 호환성 검증 테스트 미정의
7. axe 접근성 검사 누락 (하네스 의무)
8. `auth_events` enum 변경의 마이그레이션 영향 사전 확인 필요
9. grep 범위(소스 한정 vs 빌드 산출물 포함) 명시화

## 누락된 영향 파일
- `api/requirements.txt` — `pyotp` 제거
- `shared/auth_tokens.py` — `totp_setup_required` 처리 제거
- `shared/tests/test_host_classifier.py` — 동반 삭제

## 재작성 권고
해당 없음 (PASS). 위 9건은 [6] 태스크 분해에서 반드시 반영.
