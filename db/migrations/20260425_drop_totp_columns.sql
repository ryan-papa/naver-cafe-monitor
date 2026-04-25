-- 2FA(TOTP) 완전 제거: users 테이블의 TOTP 관련 컬럼 DROP
-- PRD: docs/prd/20260425_110026_remove-2fa_90a6c197/prd.md
-- 롤백: db/migrations/20260425_drop_totp_columns_down.sql

USE naver_cafe_monitor;

ALTER TABLE users
    DROP COLUMN IF EXISTS totp_secret_enc,
    DROP COLUMN IF EXISTS totp_enabled,
    DROP COLUMN IF EXISTS backup_codes_hash;
