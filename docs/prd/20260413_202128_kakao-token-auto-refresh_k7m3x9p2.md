# PRD: 카카오 토큰 자동 갱신

**ID:** 20260413_202128_kakao-token-auto-refresh_k7m3x9p2
**날짜:** 2026-04-13
**상태:** Approved

---

## 개요·목적

- **배경:** 카카오 access token은 6시간마다 만료되어 배치(30분 주기) 실행 시 하루 여러 번 전송 실패 발생. 현재 수동으로 토큰을 교체해야 하며, refresh token 갱신 로직이 없음
- **목표:** refresh token 기반 자동 갱신으로 카카오톡 전송 무중단 운영 + refresh token 만료 사전 알림
- **범위:** `KakaoAuth` 클래스 신규, `KakaoMessenger` 리팩터링, 토큰 저장 파일, 셋업 스크립트, 만료 알림

---

## 사용자 스토리

| As a | I want | So that |
|------|--------|---------|
| 운영자 | access token이 자동으로 갱신되길 | 수동 토큰 교체 없이 배치가 계속 동작한다 |
| 운영자 | refresh token 만료 14일 전 알림을 받길 | 만료 전에 재인증하여 서비스 중단을 방지한다 |
| 운영자 | 최초 토큰 셋업을 스크립트로 자동화하길 | 브라우저 인증 → 토큰 발급까지 한 번에 완료한다 |

---

## 기능 요구사항

| ID | 요구사항 | 우선순위 | AC (완료 조건) |
|----|----------|----------|---------------|
| F-13 | `KakaoAuth` 클래스: 토큰 로드/저장/갱신 책임 분리. `KakaoMessenger`와 독립적으로 테스트 가능한 인터페이스 | High | 단위 테스트에서 mock 카카오 API로 토큰 갱신 성공/실패 검증 |
| F-14 | `config/kakao_token.json`에 access_token, refresh_token, expires_at, refresh_token_expires_at 저장. 파일 손상 시(빈 파일, 잘못된 JSON) 명확한 에러 메시지 출력 후 배치 중단 | High | 손상된 JSON 파일로 시작 시 `InvalidTokenFile` 에러 발생 확인 |
| F-15 | API 401 응답 시 refresh token으로 access token 갱신 후 재시도 (1회만). 401 외 에러(403, 429 등)는 갱신 없이 즉시 에러 발생 | High | mock 서버에서 401 → 갱신 → 재시도 성공 / 403 → 즉시 에러 검증 |
| F-16 | 갱신 성공 시 `kakao_token.json` 자동 업데이트. 카카오 API 응답에 새 refresh_token이 없으면 기존 값 유지 | High | 응답에 refresh_token 포함/미포함 두 케이스 모두 검증 |
| F-17 | refresh token 만료 14일 전부터 하루 1회 WARNING 로그 출력 (KST 기준 날짜, 남은 일수 포함) | Mid | expires_at을 14일 이내로 설정 후 WARNING 로그 출력 확인 |
| F-18 | refresh token 만료 14일 전부터 하루 1회 카카오톡 나에게 보내기로 알림 전송 | Mid | 알림 전송 후 `last_alert_date` 업데이트 확인 |
| F-19 | 알림 중복 방지: `kakao_token.json`의 `last_alert_date`(KST 날짜 문자열)로 당일 전송 여부 체크 | Mid | 같은 날 2회 실행 시 알림 1회만 전송 확인 |
| F-20 | `scripts/kakao_setup.py`: 로컬 HTTP 서버(port 9999) 기동 → 브라우저 자동 오픈 → 인가 코드 수신 → 토큰 발급 → `kakao_token.json` 저장. redirect_uri는 `http://localhost:9999/callback` | Mid | 스크립트 실행 후 `kakao_token.json` 생성 및 유효 토큰 포함 확인 |
| F-21 | `.env`에서 `KAKAO_TOKEN` 제거, `KAKAO_CLIENT_ID`와 `KAKAO_CLIENT_SECRET` 추가. `config.py`의 `_REQUIRED_ENV_VARS` 및 `Config` 클래스 프로퍼티 동기 수정 | High | `KAKAO_TOKEN` 없이 배치 정상 시작 확인 |
| F-22 | `KakaoMessenger`가 `KakaoAuth`를 주입받아 토큰 사용. `batch.py`의 `KakaoMessenger.from_config` 호출부도 `KakaoAuth` 경유로 변경 | High | `batch.py` 정상 실행 + `KakaoAuth` mock 주입 테스트 통과 |

---

## 비기능 요구사항

| 항목 | 요구사항 |
|------|----------|
| 하위 호환 | 기존 배치 실행 명령(`python -m src.batch`, `bash scripts/start.sh`) 변경 없음 |
| 보안 | client_secret은 `.env`에, 토큰은 `config/kakao_token.json`에 분리 저장. 두 파일 모두 `.gitignore` 포함 |
| 안정성 | refresh token 갱신 실패 시 에러 로그(ERROR 레벨) + 배치 중단. 재시도 없음 (다음 cron 주기에서 자연 재시도) |
| 동시성 | `kakao_token.json` 파일 쓰기 시 임시 파일 → atomic rename 패턴 사용 (cron 중첩 실행 대응) |
| 관측가능성 | 토큰 갱신 성공 시 INFO 로그 ("access token 갱신 완료"), 실패 시 ERROR 로그 (상태 코드 + 응답 본문 포함) |
| 셋업 스크립트 | 로컬 서버 포트: 9999 (충돌 시 에러 메시지 출력). redirect_uri: `http://localhost:9999/callback` |

## 테스트 전략

| 레벨 | 대상 | 방법 |
|------|------|------|
| 단위 | `KakaoAuth` 토큰 로드/저장/갱신 | mock HTTP 응답으로 401 재시도, 갱신 성공/실패, refresh_token 유무 케이스 검증 |
| 단위 | `KakaoAuth` 만료 알림 판정 | expires_at 조작으로 14일 이내/이후/당일 중복 검증 |
| 통합 | `KakaoMessenger` + `KakaoAuth` | mock auth 주입 후 `send_text` → 401 → 갱신 → 재시도 플로우 검증 |
| 통합 | 토큰 파일 I/O | 손상 JSON, 빈 파일, 권한 없음 등 엣지 케이스 |

---

## 연쇄 변경 대상

| 파일 | 변경 내용 |
|------|----------|
| `src/config.py` | `_REQUIRED_ENV_VARS`에서 `KAKAO_TOKEN` 제거, `KAKAO_CLIENT_ID`·`KAKAO_CLIENT_SECRET` 추가. `Config` 클래스에 `kakao_client_id`, `kakao_client_secret` 프로퍼티 추가 |
| `src/batch.py` | `KakaoMessenger.from_config` → `KakaoAuth` 생성 후 `KakaoMessenger`에 주입 |
| `src/messaging/kakao.py` | `__init__`에서 `access_token: str` → `auth: KakaoAuth` 주입. `_send_template`에서 401 시 `auth.refresh()` 호출 후 재시도 |
| `.env` | `KAKAO_TOKEN` 제거, `KAKAO_CLIENT_ID`·`KAKAO_CLIENT_SECRET` 추가 |

---

## 제약사항

- 기술: 카카오 refresh token 유효기간 60일, 만료 30일 전부터 갱신 시 자동 연장
- 기술: 카카오 API 갱신 응답에 새 refresh_token이 포함되지 않을 수 있음 → 기존 값 유지
- 기술: 카카오 클라이언트 시크릿 활성화 필수 (현재 앱 설정)
- 비즈니스: 셋업 스크립트는 최초 1회 + refresh token 만료 시에만 실행

---

## 토큰 저장 구조

`config/kakao_token.json`:
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_at": 1713045600,
  "refresh_token_expires_at": 1718229600,
  "last_alert_date": "2026-04-13"
}
```

---

## 성공 지표

| 지표 | 목표값 | 측정 조건 |
|------|--------|-----------|
| access token 만료로 인한 전송 실패 | 0건 | 자동 갱신 적용 후 월 집계 |
| refresh token 만료 사전 알림 도달 | 만료 14일 전 첫 알림 | 알림 시점 로그 확인 |
| 셋업 스크립트 완료 시간 | 30초 이내 | 브라우저 인증 제외 |

---

## Open Issues

| ID | 항목 | 내용 | 우선순위 |
|----|------|------|----------|
| - | - | 현재 미결 이슈 없음 | - |

---

## Review 결과

### 기획 리뷰 (Planning Review)

| 회차 | 명확성 | 완성도 | 실현가능성 | 일관성 | 측정가능성 | 간결성 | 적정크기 | 평균 |
|------|--------|--------|-----------|--------|-----------|--------|---------|------|
| 1 | 9 | 9 | 9 | 9 | 8 | 9 | 9 | 8.86 |

**판정:** 8.86 / 10 → 통과
**피드백:**
- [측정가능성 -2] 전송 실패 0건의 측정 방법 미명시, 셋업 스크립트 시간 측정 시 브라우저 인증 분리 어려움

### 엔지니어링 리뷰 (Engineering Review)

| 회차 | 요구사항 명확성 | 기술적 실현가능성 | 범위·공수 | NFR | 의존성·리스크 | 테스트 가능성 | 평균 |
|------|---------------|-----------------|----------|-----|-------------|-------------|------|
| 1 | 8 | 9 | 8 | 6 | 7 | 5 | 7.17 |
| 2 | 9 | 9 | 8 | 8 | 8 | 8 | 8.33 |

**판정:** 8.33 / 10 → 통과
**피드백 (1회차):**
- [NFR -4] 갱신 실패 재시도 정책·동시 쓰기 경쟁조건·파일 손상 복구·관측가능성 부재
- [의존성리스크 -3] refresh_token 미반환 케이스 미고려, `.env` 마이그레이션 계획 부재
- [테스트가능성 -5] AC 전무, 테스트 전략 부재

**피드백 (2회차):**
- [NFR -2] 네트워크 일시 장애와 영구 실패 구분 없이 일률적 처리
- [의존성리스크 -2] `.env` 마이그레이션 절차(순서, 다운타임) 미명시
- [테스트가능성 -2] F-20 셋업 스크립트 자동화 테스트 방법 미기술

### 최종 판정

기획 8.86 + 엔지니어링 8.33 → `Approved`
