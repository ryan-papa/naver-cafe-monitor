-- 롤백: 2FA(TOTP) 컬럼 복원
-- 주의: 컬럼만 복원하며, 기존 데이터는 모두 NULL/false 로 초기화. TOTP 시크릿 재발급 필요.

USE naver_cafe_monitor;

ALTER TABLE users
    ADD COLUMN totp_secret_enc   VARBINARY(255) DEFAULT NULL
        COMMENT 'TOTP secret 의 AES-GCM 암호문',
    ADD COLUMN totp_enabled      BOOLEAN NOT NULL DEFAULT FALSE
        COMMENT '2FA 활성화 여부',
    ADD COLUMN backup_codes_hash JSON DEFAULT NULL
        COMMENT '백업 코드 argon2 해시 배열 (JSON)';
