# 코드 리뷰 r1

## 점수표
| 항목 | 점수 | 근거 |
|------|------|------|
| 정확성 | 9.0 | TOTP 흐름·`LoginContext.internal`·`host_classifier`·`setup_required` 분기 모두 삭제. 핵심 인증 보존. F-15 자연 처리 |
| 보안 | 8.5 | argon2/AES/HMAC/RSA/CSRF/rate-limit 보존. 외부 차단 인프라 단일 의존이지만 코드 회귀 없음 |
| 일관성 | 7.5 | 영향 파일 표와 diff 거의 일치. PRD grep 게이트와 의도 잔존 사이 형식 모순. `backup_codes_hash` DROP 이 PRD 미명시 |
| 테스트 커버리지 | 7.5 | F-15 단위 테스트 신규. auth_events 부분집합 단언 강화. redirects.spec 의 `[302, 404]` 허용은 라우트 제거 검증력 약함 |
| 가독성 | 9.0 | docstring/__all__ 갱신. dead code 흔적 없음. legacy 보존 사유 docstring 명시 |
| 성능 | 9.0 | idempotent ALTER, 단일 운영자 무영향. 런타임 분기 제거로 미미한 단축 |
| 운영 안전 | 8.0 | IF EXISTS + 별도 down. F-15 호환성. down 데이터 손실 PRD 강조 약함 |

## 평균 / 최저
- 평균: 8.36
- 최저: 7.5 (일관성, 테스트 커버리지)

## 합격 여부
PASS (평균 8.0+, 최저 7.0+)

## 강점
- F-15 호환성을 verify_token 구조로 자연 처리 + 회귀 가드 테스트
- legacy enum 보존 + Python 발행 차단 단언 분리
- pyotp·host_classifier·SETUP_ALLOWED_PREFIXES 등 보조 표면 일괄 제거
- 마이그레이션 idempotent + 별도 down + 기존 마이그레이션 무수정
- README 동시 갱신 일관성

## 약점·구체 지적
1. `web/tests/e2e/redirects.spec.ts:21-29` — `/admin/settings/2fa` 가 미인증으로 항상 302 분기. 인증 세션 케이스 추가 권장
2. `db/migrations/20260425_drop_totp_columns.sql:10` — `backup_codes_hash` DROP 이 PRD F-06 미명시
3. PRD `prd.md:88` — grep 0 hit 게이트와 의도 잔존(F-15 테스트, 마이그레이션 본문) 형식 모순. 예외 주석 보강
4. PRD 롤백 표 — down 시 데이터 손실(시크릿 NULL 초기화) 명시 약함
5. `/settings/2fa` legacy redirect 제거의 e2e 가드 부재

## 잠재 회귀
- mTLS 인프라 미적용 시 외부 노출 위험 (코드 책임 아님, 배포 사전 점검 필수)
- 향후 verify_token 이 dict 동적 클레임을 도입하면 F-15 자연 무시 깨질 가능성. 가드 주석 + 테스트로 방어

## 재작업 권고
해당 없음 (PASS). 약점 1·2·3·4 는 머지 차단 아니나 후속 커밋 1회로 반영 권장.
