# PRD: 회원가입·로그인 (Auth MVP)

**ID:** 20260417_202717_auth-signup-login_ad69d7f7
**날짜:** 2026-04-17
**상태:** In Review (v2)
**개정:** 2026-04-17 2FA 도메인별 정책 · `/settings/2fa` 추가

---

## 문제·맥락

| 항목 | 내용 |
|------|------|
| 배경 | 현재 서비스는 mTLS로 내부 접근만 가능. 외부 공개 예정(`ncm.eepp.store`)이라 사용자 인증 체계 부재. |
| 원인 | 인증 레이어 없음. 누구나 접근 가능한 구조로 공개 시 위험. |
| 왜 지금 | 외부 도메인 연결 전에 인증·세션·접근 제어 선행 필요. |

## 타깃 사용자

| 항목 | 내용 |
|------|------|
| 대상 사용자 | 네이버 카페 모니터링 이력·재발송을 외부에서 확인해야 하는 운영자·협업자 |
| 사용 맥락 | 이동 중·자택에서 모바일/PC 브라우저로 접근. 민감 알림 내역 보호 필요. |
| 핵심 동기 | 안전하게 개인 계정으로 접근, 2FA로 탈취 방어 |

## 핵심 시나리오

| # | 장면 | 사용자 행동 | 시스템 반응 |
|---|------|-----------|-----------|
| 1 | 첫 방문 | URL 진입 | 미인증 감지 → `/login` 301 |
| 2 | 회원가입 | 이메일·이름·비번 입력 → 제출 | 중복·정책 검증 → TOTP QR + 백업코드 표시 |
| 3 | TOTP 등록 | Authenticator 스캔 → 6자리 입력 | 검증 성공 → 활성화 → 자동 로그인 → 대시보드 |
| 4 | 재방문 로그인 | 이메일·비번 → 6자리 TOTP | 쿠키 발급 (access 1h, refresh 24h) → 대시보드 |
| 5 | 세션 만료 | access 만료 시 API 호출 | refresh로 자동 회전, 실패 시 `/login` |
| 6 | 타 기기 로그인 | 동일 계정으로 새 기기 로그인 | 기존 refresh 무효화, 이전 기기 401 |
| 7 | 탈취 의심 | 폐기된 refresh 재사용 감지 | 해당 user 전체 세션 무효화 + `auth_events` 로그 |

**실패 모드:**

| 코드경로 | 시나리오 | 감지 | UX 대응 |
|----------|----------|------|---------|
| 로그인 | 비번 5회 실패 | 계정 잠금 15분 | "잠시 후 다시 시도" 안내 + 남은 시간 |
| 로그인 | IP 10회 실패 | IP 15분 차단 | 429 + 안내 페이지 |
| 가입 | 이메일 중복 | HMAC 인덱스 조회 | 필드 에러 "이미 가입된 이메일" |
| 가입 | 비번 정책 미달 | 서버·클라 이중 검증 | 규칙 표시 + 필드 에러 |
| TOTP | 6자리 오류 | 30s 윈도우 검증 | "코드가 올바르지 않습니다" |
| E2E | 공개키 로드 실패 | 클라 fetch 실패 | "페이지 새로고침" 안내 모달 |
| 네트워크 | API 5xx | 전역 인터셉터 | `/error/500` + 재시도 |
| 라우팅 | 없는 경로 | Astro 미들웨어 | `/error/404` |

## 스코프

| 포함 (In) | 비포함 (Out) |
|-----------|-------------|
| 이메일·이름 AES-GCM 암호화 (HMAC 룩업) | 이메일 인증 메일 발송 |
| 비번 argon2id 해시 | 비밀번호 재설정 (관리자 문의 안내) |
| JWT (access 1h / refresh 24h), httpOnly Secure Cookie | SSO·소셜 로그인 |
| Refresh rotation + 재사용 감지 | 다중 세션 (단일 세션만) |
| TOTP 전 사용자 필수 + 백업코드 10개 | SMS OTP |
| IP + 계정 이중 rate limit | 권한(role) 체계 (TODO로 남김, `is_admin` 컬럼만 시드) |
| 에러 페이지 (401/403/404/500/offline) 커스텀 | 다국어 |
| E2E: 민감 필드 RSA-OAEP 공개키 암호화 | 요청 전체 ECDH |
| 초기 관리자 시드 스크립트 | 가입 승인 플로우 |

## 대안 탐색 (A/B/C/D)

### 1) 필드 암호화

| 대안 | 요약 | 장·단점 | 공수 | 판단 근거 |
|------|------|---------|------|----------|
| A | **AES-GCM(email/name) + HMAC 인덱스 + argon2id(비번)** | 조회·중복체크 가능, 암호·해시 이중 방어 / 구현 복잡 | 중 | 제품 가설 (민감 노출 차단) |
| B | 비번만 argon2, 이메일·이름 평문 | 단순 / 평문 노출 | 하 | 엔지니어 선호 |
| C | 전체 AES-GCM (비번 포함) | 복호화 가능 / 비번 복호화는 보안 악 | 중 | — |
| D | 현상 유지(인증 없음) | — | — | — |

**선택:** A · **근거 유형:** 제품 가설

### 2) 토큰 저장

| 대안 | 요약 | 장·단점 | 공수 | 판단 근거 |
|------|------|---------|------|----------|
| A | **httpOnly Secure Cookie + CSRF** | XSS 방어, 자동 전송 / CSRF 별도 | 중 | 제품 가설 |
| B | localStorage + Authorization 헤더 | 단순 / XSS 취약 | 하 | 엔지니어 선호 |
| C | access=메모리, refresh=Cookie 하이브리드 | 보안 양호 / 구현 복잡 | 중 | — |
| D | 현상 유지 | — | — | — |

**선택:** A · **근거 유형:** 제품 가설

### 3) 라우팅 가드

| 대안 | 요약 | 장·단점 | 공수 | 판단 근거 |
|------|------|---------|------|----------|
| A | **Astro SSR + 미들웨어** | UX·보안 균형 / SSR 전환 필요 | 중 | 제품 가설 |
| B | 클라 가드 (`/api/auth/me`) | 단순 / 깜빡임 | 하 | 엔지니어 선호 |
| C | nginx `auth_request` | 강력 / 설정 복잡 | 중 | — |
| D | 현상 유지 | — | — | — |

**선택:** A · **근거 유형:** 제품 가설

### 4) 2FA (v2 개정)

| 대안 | 요약 | 장·단점 | 공수 | 판단 근거 |
|------|------|---------|------|----------|
| A | 선택 기능 | 사용자 편의 / 보안 불균질 | 하 | — |
| B | 관리자만 필수 | 보안·편의 균형 / 이원화 | 중 | — |
| C | 전 사용자 필수 | 보안 강함 / 내부망에도 강제되어 중복 방어 | 중 | — |
| **C'** | **도메인 기반: 외부(`*.eepp.store`)만 필수, 내부(`*.eepp.shop`)는 mTLS 로 1차 방어, 2FA 면제** | 보안 계층 분리 · 운영자 편의 · 외부 공개 시 자동 강제 | 중 | 창업자 직감 |
| D | 미도입 | — | — | — |

**선택:** C' · **근거 유형:** 창업자 직감 (내부 mTLS 는 실질적 2요소 역할)

### 5) Refresh 관리

| 대안 | 요약 | 장·단점 | 공수 | 판단 근거 |
|------|------|---------|------|----------|
| A | **DB 저장 + Rotation + 재사용 감지** | OAuth 표준, 탈취 대응 | 중 | 제품 가설 |
| B | DB 저장, 회전 없음 | 단순 / 탈취 대응 약 | 하 | — |
| C | Stateless | 단순 / 폐기 불가 | 하 | — |
| D | DB+회전+디바이스별 | 강함 / 현 MVP 과대 | 상 | — |

**선택:** A · **근거 유형:** 제품 가설

### 6) 세션

| 대안 | 요약 | 장·단점 | 공수 | 판단 근거 |
|------|------|---------|------|----------|
| A | 다중 세션 | 편의 / 관리 복잡 | 중 | — |
| B | **단일 세션** | 단순·탈취 방어 / 기기 전환 시 재로그인 | 하 | 창업자 직감 |
| C | 다중 + 전체 로그아웃 API | 편의+안전 / 공수↑ | 중 | — |
| D | — | — | — | — |

**선택:** B · **근거 유형:** 창업자 직감

### 7) E2E 암호화

| 대안 | 요약 | 장·단점 | 공수 | 판단 근거 |
|------|------|---------|------|----------|
| A | **민감 필드 RSA-OAEP 공개키 암호화** | TLS 이후 평문 차단 / 키 관리 | 중 | 창업자 직감 |
| B | 요청 본문 ECDH+AES-GCM | 완전 E2E / 디버깅 난이도 | 상 | — |
| C | 클라 pre-hash | 단순 / E2E 약 | 하 | — |
| D | HTTPS만 | 단순 / 터미널 평문 가능 | 0 | 엔지니어 선호 |

**선택:** A · **근거 유형:** 창업자 직감

### 8) 최초 관리자

| 대안 | 요약 | 장·단점 | 공수 | 판단 근거 |
|------|------|---------|------|----------|
| A | **시드 스크립트 (env 1회)** | 자동화·반복 가능 / 환경변수 관리 | 하 | 제품 가설 |
| B | 첫 가입자 자동 관리자 | 단순 / 선점 악용 가능 | 하 | — |
| C | 공개 가입 + 권한 TODO | 단순 / 운영자 구분 없음 | 하 | — |
| D | 폐쇄 가입, 수동 등록 | 안전 / 등록 번거로움 | 중 | — |

**선택:** A · **근거 유형:** 제품 가설

## 성공·실패 기준

| 구분 | 지표 | 목표값 |
|------|------|--------|
| 성공 | 로그인 성공률 | > 99% (정상 credential) |
| 성공 | TOTP 등록 완료율 | > 95% |
| 성공 | p95 로그인 API 응답 | < 500ms |
| 실패(접음) | rate limit 오탐률 | > 1% |

## 사용자 검증 게이트

| 단계 | 방법 | 합격 기준 |
|------|------|----------|
| 1. 내부 시범 사용 (dogfooding) | 운영자(본인 계정 `hosekim92@naver.com`)가 가입→TOTP→로그인→세션 회전 전 플로우를 3일간 실사용 | 중단·막힘 없이 주요 시나리오(#1~#7) 완주 |
| 2. 동료 1명 초대 검증 | 협업자 1명에게 계정 발급·안내 후 모바일·PC에서 접근 | 설명 없이 가입·TOTP 등록 완료, 30분 내 |
| 3. 에러 페이지 수동 테스트 | 의도적 401/403/404/500/offline 유발 | 각 페이지 커스텀 디자인 노출 및 "홈으로" 동작 |
| 4. 보안 검사 (수동) | 쿠키 플래그(HttpOnly/Secure/SameSite), CSRF 토큰, E2E 필드 암호문 확인 | 개발자도구·프록시로 실제 암호문 확인 |
| 5. 탈취 시나리오 리허설 | 쿠키 복제 후 동일 계정 새 로그인 → 폐기된 refresh 재사용 시도 | 즉시 401 + `auth_events.refresh_reuse_detected` 기록 |

**MVP 판단 근거:** 외부 오픈 전 단계이므로 실사용자 A/B 대신 **내부 시범(dogfooding) + 동료 1명 초대**로 게이트를 대체. 실사용자 반응은 외부 오픈 후 로그 기반 관찰.

## 리스크·열린 질문

| 유형 | 내용 | 대응 |
|------|------|------|
| 리스크 | RSA 개인키 유출 | `.env.enc` sops 관리, 주기 rotation 절차 문서화 |
| 리스크 | TOTP 기기 분실 | 백업 코드 10개 (1회용) 복사 안내 |
| 리스크 | `is_admin` 상승 오남용 | 현재 직접 DB 수정만 허용 (API 미제공) |
| 열린 질문 | 관리자 권한 확장 시 role 테이블 설계 | TODO, 후속 PRD |
| 열린 질문 | 백업 코드 재발급 UX | 1차 릴리스 후 UX 관찰 |

---

## 기능 요구사항

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| F-01 | 회원가입: 이메일·이름·비번 입력 + 정책 검증 | Must |
| F-02 | 이메일 중복 체크 (HMAC 인덱스) | Must |
| F-03 | 비번 argon2id 해시, 이메일·이름 AES-GCM 암호화 | Must |
| F-04 | TOTP 최초 설정 (QR + 백업코드 10개) | Must |
| F-05 | 로그인: 이메일·비번 → TOTP → 쿠키 발급 | Must |
| F-06 | 로그인 실패 보호: IP+계정 이중 rate limit | Must |
| F-07 | Refresh rotation + 재사용 감지 → 전체 세션 무효화 | Must |
| F-08 | 단일 세션: 새 로그인 시 기존 refresh 폐기 | Must |
| F-09 | 로그아웃: 쿠키 제거 + refresh DB 삭제 | Must |
| F-10 | Astro SSR 미들웨어 가드: 미인증 시 `/login` 301 | Must |
| F-11 | E2E: `/api/auth/public-key` → 클라가 비번·이메일 RSA-OAEP 암호화 후 전송 | Must |
| F-12 | 에러 페이지 401/403/404/500/offline + 공통 디자인 | Must |
| F-13 | 초기 관리자 시드 스크립트 (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD` 환경변수 1회 사용) | Must |
| F-14 | `is_admin` 컬럼 (bool) 스키마 반영, API 미노출 | Must (TODO 권한 체계 대비) |
| F-15 | `auth_events` 로그 테이블 (로그인/실패/재사용 감지/토큰 회전) | Should |
| F-16 | 2FA 재설정 API + 페이지 `/settings/2fa` (비번 + TOTP/백업코드 재확인 → 새 QR·백업코드 10개) | Must |
| F-17 | 호스트 분류: `*.eepp.shop`=internal, `*.eepp.store`=external (suffix 매칭) | Must |
| F-18 | 외부 로그인 성공 & TOTP 미설정 → JWT claim `totp_setup_required=true`. 내부 로그인은 claim 미부여 (2FA 면제) | Must |
| F-19 | 반쪽 세션 가드: 백엔드(`current_user`)는 `/api/auth/*` + `/api/settings/2fa/*` 외 요청 반려(403). 프론트 미들웨어는 `/api/auth/me` 응답 기반 `/settings/2fa` 강제 리다이렉트 | Must |
| F-20 | `/settings/2fa` 단일 페이지: 미설정 → QR·백업코드 확인 UI, 설정됨 → 재확인(비번 + TOTP OR 백업코드) → 신규 발급 | Must |

## 비기능 요구사항

| 항목 | 요구사항 |
|------|----------|
| 보안 | TLS + httpOnly Cookie + CSRF 토큰 + E2E 필드 암호화 + argon2id + TOTP |
| 성능 | p95 로그인 < 500ms, argon2 파라미터 m=64MB/t=3/p=1, RSA-2048 |
| 가용성 | 단일 Mac Mini, 기존 배포 플로우 유지 |
| 로깅 | 비밀번호·TOTP·토큰 평문 로그 금지. `auth_events`는 user_id·event_type·ip·ua만 |
| 시크릿 | 모든 키는 `.env.enc` (sops+age). 문서·커밋·로그에 평문 금지 |

## 쿠키·CSRF 상세

| 쿠키 | 속성 |
|------|------|
| `access_token` | HttpOnly, Secure, SameSite=Strict, Path=/, Max-Age=3600 |
| `refresh_token` | HttpOnly, Secure, SameSite=Strict, Path=/api/auth, Max-Age=86400 |
| `csrf_token` | Secure, SameSite=Strict, **HttpOnly=false** (JS 접근 필요), Max-Age=3600 |

- **CSRF 전달 방식:** Double-submit cookie. 모든 state-changing 요청(`POST/PATCH/DELETE`)에 `X-CSRF-Token` 헤더 필수. 서버가 `csrf_token` 쿠키값과 헤더값 비교.
- **도메인:** `ncm.eepp.shop` 단일 도메인 한정. 서브도메인 공유 없음.

## Rate Limit 구현

| 항목 | 내용 |
|------|------|
| 저장소 | MySQL `rate_limit_buckets` (Redis 미도입 단계) |
| 갱신 | INSERT ... ON DUPLICATE KEY UPDATE (원자성 확보) |
| 정리 | 배치 cron: 만료 버킷 1시간마다 삭제 |
| 정책 | IP: 5분 10회, 계정: 5분 5회, 초과 시 15분 lock |

## 키 관리·Rotation 절차

| 키 | 저장 | Rotation 주기 | 절차 |
|----|------|--------------|------|
| RSA (E2E) | `.env.enc` (priv), 공개키 API로 배포 | 6개월 | 새 키쌍 생성 → 공개키 API에 병행 노출(2주) → 구키 폐기 |
| AES (email/name 암호화) | `.env.enc` | 12개월 | 새 키로 데이터 재암호화 배치 → 구키 폐기 |
| HMAC (email 인덱스) | `.env.enc` | 불변 (바뀌면 인덱스 재계산 필요, 정책상 고정) | — |
| JWT secret | `.env.enc` | 탈취 의심 시 즉시 | 교체 → 모든 refresh 무효화 → 강제 재로그인 |
| TOTP secret | `users.totp_secret_enc` | 사용자 요청 시 (비번 재확인) | 재발급 QR + 백업코드 |

## 장애·운영 시나리오

| 시나리오 | 대응 |
|----------|------|
| TOTP 기기 분실, 백업코드 남음 | 사용자: 백업코드로 로그인 → 2FA 재설정 |
| TOTP 기기 분실, 백업코드 소진 | 관리자: DB에서 `totp_enabled=false` + 비번 임시 초기화 → 사용자 재설정 |
| 관리자 계정 TOTP 분실 | sops 복호화 가능한 다른 age 키 소유자가 DB 직접 수정 |
| RSA 개인키 유출 의심 | 즉시 rotation (위 절차). 유출 기간 내 가입·로그인 데이터는 재검토 |
| DB 유출 | 이메일·이름 암호문, 비번 argon2, TOTP 암호문 → 직접 노출 없음. 단, argon2 오프라인 크래킹 대응해 전 사용자 비번 초기화 |
| rate limit 오탐 (사내 NAT) | 관리자 DB에서 해당 `rate_limit_buckets` row 삭제 |

## 데이터 모델

### `users`
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | BIGINT PK | |
| email_enc | VARBINARY(512) | AES-GCM 암호문 |
| email_hmac | VARBINARY(32) UNIQUE | HMAC-SHA256 룩업 인덱스 |
| name_enc | VARBINARY(512) | AES-GCM 암호문 |
| password_hash | VARCHAR(255) | argon2id |
| totp_secret_enc | VARBINARY(255) | AES-GCM 암호문 |
| totp_enabled | BOOL | |
| backup_codes_hash | JSON | argon2 해시 배열 (1회용) |
| is_admin | BOOL default false | TODO: 권한 체계 |
| failed_login_count | INT default 0 | |
| locked_until | DATETIME NULL | |
| created_at / updated_at | DATETIME | |

### `refresh_tokens` (단일 세션)
| 컬럼 | 타입 |
|------|------|
| user_id | BIGINT PK (FK) |
| token_hash | VARCHAR(64) UNIQUE (SHA-256) |
| issued_at | DATETIME |
| expires_at | DATETIME |
| rotated_from | VARCHAR(64) NULL (재사용 감지용) |

### `auth_events`
| 컬럼 | 타입 |
|------|------|
| id | BIGINT PK |
| user_id | BIGINT NULL |
| event_type | ENUM (`login_ok`, `login_fail`, `signup`, `totp_ok`, `totp_fail`, `refresh_rotated`, `refresh_reuse_detected`, `logout`, `locked`) |
| ip | VARCHAR(45) |
| user_agent | VARCHAR(255) |
| created_at | DATETIME |

### `rate_limit_buckets` (in-memory 또는 DB)
| 컬럼 | 타입 |
|------|------|
| key | VARCHAR(128) (`ip:1.2.3.4` 또는 `user:42`) |
| count | INT |
| window_end | DATETIME |

## API 개요

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/auth/public-key` | RSA 공개키 (PEM) |
| POST | `/api/auth/signup` | `{email_enc, name_enc, password_enc}` → `{totp_secret, qr_url, backup_codes}` |
| POST | `/api/auth/signup/confirm` | `{email_enc, totp_code}` → 활성화 + 쿠키 발급 |
| POST | `/api/auth/login` | `{email_enc, password_enc, totp_code}` → 쿠키 발급 |
| POST | `/api/auth/refresh` | (쿠키) → 새 access + refresh |
| POST | `/api/auth/logout` | (쿠키) → 무효화 |
| GET | `/api/auth/me` | 현재 사용자 정보 |

## 비밀번호·TOTP 정책

- 비밀번호: 최소 10자, 영문+숫자+특수문자 (서버·클라 이중 검증)
- TOTP: 30초 윈도우, 6자리, ±1 윈도우 허용
- 백업 코드: 10개, 영숫자 10자리, 1회용, argon2 해시 저장

## 라우팅/에러 페이지

| Path | 용도 |
|------|------|
| `/login` | 로그인 |
| `/signup` | 회원가입 (3단계: 정보→TOTP→완료) |
| `/settings/2fa` | 2FA 최초 설정 + 재설정 (v2 신규) |
| `/error/401` | 미인증 |
| `/error/403` | 권한 없음 |
| `/error/404` | 없는 페이지 |
| `/error/500` | 서버 오류 |
| `/error/offline` | 네트워크 오류 |

## v2 스펙 상세 (2FA 도메인별 정책)

### 호스트 분류

| 호스트 suffix | 분류 | 2FA 정책 |
|---------------|------|----------|
| `.eepp.shop` | internal | 면제 (mTLS 로 1차 방어) |
| `.eepp.store` | external | 필수 |
| 기타 | unknown | 기본 external 로 처리 (안전 측) |

구현: `shared/host_classifier.py::classify(hostname)` → `"internal" | "external"`.

### 로그인 분기

| 조건 | 동작 |
|------|------|
| 내부 로그인 성공 | access/refresh 발급, claim 없음 |
| 외부 로그인 + `totp_enabled=True` | 기존 로직 (TOTP 코드 요구) |
| 외부 로그인 + `totp_enabled=False` | 비번만 통과해도 access 발급. 단 claim `totp_setup_required=true` 삽입. refresh 도 동일 상태 표시. |

### 반쪽 세션 가드

백엔드(`current_user`):
- `totp_setup_required=true` 토큰은 아래 경로만 허용:
  - `/api/auth/me`, `/api/auth/logout`, `/api/auth/refresh`
  - `/api/auth/public-key`
  - `/api/settings/2fa/*`
- 그 외 요청은 `403 totp_setup_required`.

프런트 SSR middleware:
- `/api/auth/me` 호출 → 200 응답의 `totp_setup_required=true` 면 `/settings/2fa` 외 경로 접근 시 302 redirect.

### `/settings/2fa` 동작

| 사용자 상태 | UI |
|-------------|-----|
| `totp_enabled=false` + secret 없음 | secret 생성·저장 (enabled 유지 false), QR + 백업코드 10개 표시, TOTP 코드 입력으로 활성화 |
| `totp_enabled=false` + secret 있음 (재진입) | 기존 QR·코드 재사용 |
| `totp_enabled=true` (재설정) | 현재 비번 + (TOTP OR 백업코드 1개) 재확인 → 새 secret + 새 백업코드 10개로 교체 → 신규 QR 표시 |

### 데이터 모델 영향

기존 `users` 테이블만으로 충분. 신규 컬럼 없음.

### 새 요구사항

| ID | 요구사항 |
|----|----------|
| F-16 | `/api/settings/2fa/*` 엔드포인트들 (`GET` 상태, `POST /enable`, `POST /reset`) + `/settings/2fa` 페이지 |
| F-17 | 호스트 분류 유틸 |
| F-18 | 외부 로그인 + TOTP 미설정 시 `totp_setup_required` claim |
| F-19 | 백엔드 전역 가드 (setup_required 시 허용 경로 화이트리스트) |
| F-20 | 프런트 미들웨어: `/api/auth/me` 응답 기반 `/settings/2fa` 강제 이동 |

## 롤아웃

1. DB 마이그레이션 (users/refresh_tokens/auth_events)
2. 시크릿 생성: RSA 키쌍, HMAC 키, AES 키 → `.env.enc`
3. 시드 스크립트 실행 (관리자 1명 생성, TOTP는 로그인 시 설정)
4. 프런트 Astro SSR 전환 + 라우팅 가드
5. mTLS는 당분간 유지, 외부 오픈 시점에 해제 + `ncm.eepp.store` 연결

## 테스트 범위

| 레벨 | 대상 |
|------|------|
| Unit | 암호화 유틸, argon2 해시, TOTP 검증, rate limit |
| Integration | signup→TOTP→login→refresh rotation→logout 풀 플로우 |
| Security | 재사용 감지, 잠금 해제, CSRF 검증 |
| E2E | Playwright: 가입·로그인·에러 페이지 접근 |
