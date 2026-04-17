-- TA-02: Auth 기능용 테이블 추가 (users, refresh_tokens, auth_events, rate_limit_buckets)
-- PRD: docs/prd/20260417_202717_auth-signup-login_ad69d7f7.md

USE naver_cafe_monitor;

-- 사용자
CREATE TABLE IF NOT EXISTS users (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    email_enc           VARBINARY(512) NOT NULL COMMENT 'AES-GCM 암호문 (iv+ciphertext+tag)',
    email_hmac          VARBINARY(32)  NOT NULL COMMENT 'HMAC-SHA256 룩업 인덱스',
    name_enc            VARBINARY(512) NOT NULL COMMENT 'AES-GCM 암호문',
    password_hash       VARCHAR(255)   NOT NULL COMMENT 'argon2id',
    totp_secret_enc     VARBINARY(255) DEFAULT NULL COMMENT 'AES-GCM 암호문, 설정 전 NULL',
    totp_enabled        BOOLEAN        NOT NULL DEFAULT FALSE,
    backup_codes_hash   JSON           DEFAULT NULL COMMENT 'argon2 해시 배열 (1회용)',
    is_admin            BOOLEAN        NOT NULL DEFAULT FALSE COMMENT 'TODO: 권한 체계 확장',
    failed_login_count  INT            NOT NULL DEFAULT 0,
    locked_until        DATETIME       DEFAULT NULL,
    created_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_email_hmac (email_hmac),
    INDEX idx_locked_until (locked_until),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 리프레시 토큰 (단일 세션: user_id PK)
CREATE TABLE IF NOT EXISTS refresh_tokens (
    user_id        BIGINT       NOT NULL PRIMARY KEY,
    token_hash     CHAR(64)     NOT NULL COMMENT 'SHA-256 hex',
    issued_at      DATETIME     NOT NULL,
    expires_at     DATETIME     NOT NULL,
    rotated_from   CHAR(64)     DEFAULT NULL COMMENT '이전 토큰 hash (재사용 감지)',
    UNIQUE KEY uk_token_hash (token_hash),
    INDEX idx_expires_at (expires_at),
    CONSTRAINT fk_refresh_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 인증 이벤트 로그
CREATE TABLE IF NOT EXISTS auth_events (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT       DEFAULT NULL,
    event_type  ENUM(
        'signup','login_ok','login_fail','totp_ok','totp_fail',
        'refresh_rotated','refresh_reuse_detected','logout','locked'
    ) NOT NULL,
    ip          VARCHAR(45)  DEFAULT NULL,
    user_agent  VARCHAR(255) DEFAULT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_event_type (event_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Rate limit 버킷 (IP/계정 이중)
CREATE TABLE IF NOT EXISTS rate_limit_buckets (
    bucket_key   VARCHAR(128) NOT NULL PRIMARY KEY COMMENT 'ip:1.2.3.4 또는 user:42',
    count        INT          NOT NULL DEFAULT 0,
    window_end   DATETIME     NOT NULL,
    INDEX idx_window_end (window_end)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
