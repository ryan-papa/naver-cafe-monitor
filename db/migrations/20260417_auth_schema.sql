-- TA-02: Auth 기능용 테이블 추가 (users, refresh_tokens, auth_events, rate_limit_buckets)
-- PRD: docs/prd/20260417_202717_auth-signup-login_ad69d7f7.md
-- 스타일 가이드: ../../docs/harness-db.md

USE naver_cafe_monitor;

-- ─────────────────────────────────────────────────────────────
-- users : 사용자 계정
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY
                        COMMENT '자동 증가 PK',
    email_enc           VARBINARY(512) NOT NULL
                        COMMENT 'AES-256-GCM 암호문. layout: iv(12B)||ciphertext||tag(16B). 키=AUTH_AES_KEY',
    email_hmac          VARBINARY(32)  NOT NULL
                        COMMENT 'HMAC-SHA256(lower(email), AUTH_HMAC_KEY). 이메일 룩업/중복 체크 인덱스',
    name_enc            VARBINARY(512) NOT NULL
                        COMMENT 'AES-256-GCM 암호문 (이름). 키=AUTH_AES_KEY',
    password_hash       VARCHAR(255)   NOT NULL
                        COMMENT 'argon2id 해시 (m=64MB, t=3, p=1)',
    totp_secret_enc     VARBINARY(255) DEFAULT NULL
                        COMMENT 'TOTP secret 의 AES-GCM 암호문. 설정 전/비활성 시 NULL',
    totp_enabled        BOOLEAN        NOT NULL DEFAULT FALSE
                        COMMENT '2FA 활성화 여부. signup confirm 또는 /settings/2fa 완료 시 TRUE',
    backup_codes_hash   JSON           DEFAULT NULL
                        COMMENT '백업 코드 argon2 해시 배열 (JSON). 1회용, 매 재설정 시 교체',
    is_admin            BOOLEAN        NOT NULL DEFAULT FALSE
                        COMMENT '관리자 여부. TODO: role 기반 권한 체계로 확장 예정',
    failed_login_count  INT            NOT NULL DEFAULT 0
                        COMMENT '연속 로그인 실패 횟수. 성공 시 0 리셋',
    locked_until        DATETIME       DEFAULT NULL
                        COMMENT '계정 lockout 해제 시각. NULL=미잠금',
    created_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP
                        COMMENT '가입 시각 (서버 로컬)',
    updated_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                        COMMENT '갱신 시각',
    UNIQUE KEY uk_email_hmac (email_hmac)
                        COMMENT '이메일 중복 가입 방지. 암호문은 비결정적이라 hmac 으로 유일성 보장',
    INDEX     idx_locked_until (locked_until)
                        COMMENT 'lockout 만료 사용자 주기적 해제 배치 조회용',
    INDEX     idx_created_at (created_at)
                        COMMENT '가입일 기준 정렬·기간 조회용'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='사용자 계정. email/name 은 AES-GCM, 비번은 argon2id, TOTP secret 은 AES-GCM.';

-- ─────────────────────────────────────────────────────────────
-- refresh_tokens : 단일 세션 (user_id 가 PK)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS refresh_tokens (
    user_id        BIGINT       NOT NULL PRIMARY KEY
                   COMMENT '사용자당 1개 refresh 만 유지 (단일 세션 정책)',
    token_hash     CHAR(64)     NOT NULL
                   COMMENT 'SHA-256 hex. refresh 토큰 평문은 저장하지 않음',
    issued_at      DATETIME     NOT NULL
                   COMMENT '발급 시각 (UTC). JWT iat 과 동일',
    expires_at     DATETIME     NOT NULL
                   COMMENT '만료 시각 (UTC). 기본 issued_at+24h',
    rotated_from   CHAR(64)     DEFAULT NULL
                   COMMENT '직전 토큰 hash. 재사용 감지에 사용. 최초 발급 시 NULL',
    UNIQUE KEY uk_token_hash (token_hash)
                   COMMENT 'token_hash 로 빠른 역추적 (재사용 감지 시)',
    INDEX     idx_expires_at (expires_at)
                   COMMENT '만료 세션 일괄 삭제 배치용',
    CONSTRAINT fk_refresh_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='refresh 토큰. 단일 세션 · rotation + reuse detection.';

-- ─────────────────────────────────────────────────────────────
-- auth_events : 인증 감사 로그
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS auth_events (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY
                COMMENT '자동 증가 PK',
    user_id     BIGINT       DEFAULT NULL
                COMMENT '대상 사용자. 이메일 미식별 실패 케이스는 NULL',
    event_type  ENUM(
                    'signup', 'login_ok', 'login_fail', 'totp_ok', 'totp_fail',
                    'refresh_rotated', 'refresh_reuse_detected', 'logout', 'locked'
                ) NOT NULL
                COMMENT '인증 이벤트 유형. '
                        'signup=가입 완료 / '
                        'login_ok=로그인 성공 / '
                        'login_fail=비번·이메일 불일치 / '
                        'totp_ok=2FA 통과 (signup confirm 포함) / '
                        'totp_fail=2FA 코드 불일치 / '
                        'refresh_rotated=refresh 정상 회전 / '
                        'refresh_reuse_detected=폐기된 refresh 재사용(탈취 의심) / '
                        'logout=사용자 로그아웃 / '
                        'locked=계정 lockout 진입',
    ip          VARCHAR(45)  DEFAULT NULL
                COMMENT 'IPv4/IPv6 주소. proxy 뒤에서는 X-Forwarded-For 첫 값',
    user_agent  VARCHAR(255) DEFAULT NULL
                COMMENT 'User-Agent 헤더 앞 255자',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                COMMENT '이벤트 발생 시각',
    INDEX     idx_user_id (user_id)
                COMMENT '특정 사용자 이벤트 히스토리 조회용',
    INDEX     idx_event_type (event_type)
                COMMENT '이벤트 유형별 집계·알림 조회용 (reuse_detected 등)',
    INDEX     idx_created_at (created_at)
                COMMENT '최근 이벤트 순 조회·보관 기간 정리용'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='인증 감사 로그. 비번·토큰·이메일 원문은 기록 금지.';

-- ─────────────────────────────────────────────────────────────
-- rate_limit_buckets : IP·계정 이중 rate limit
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rate_limit_buckets (
    bucket_key   VARCHAR(128) NOT NULL PRIMARY KEY
                 COMMENT 'ip:<addr> 또는 user:<id> 형식. 중복 방지용 PK',
    count        INT          NOT NULL DEFAULT 0
                 COMMENT '현재 윈도우 내 누적 요청 수',
    window_end   DATETIME     NOT NULL
                 COMMENT '윈도우 종료 시각. 한도 도달 시 lockout 해제 시각으로 대체됨',
    INDEX     idx_window_end (window_end)
                 COMMENT '만료 버킷 purge cron 조회용'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='로그인·signup IP+계정 rate limit 버킷. 5분 윈도우, 한도 초과 시 15분 lock.';
