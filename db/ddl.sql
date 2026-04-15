-- naver_cafe_monitor DDL
-- 실행: mysql -h eepp.shop -u REDACTED_USER -p < db/ddl.sql

CREATE DATABASE IF NOT EXISTS naver_cafe_monitor
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE naver_cafe_monitor;

CREATE TABLE IF NOT EXISTS posts (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    reg_ts       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    upd_ts       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    board_id     VARCHAR(50)  NOT NULL COMMENT '게시판 식별자 (menus/6, menus/13)',
    post_id      BIGINT       NOT NULL COMMENT '게시글 번호',
    title        VARCHAR(500) NOT NULL DEFAULT '' COMMENT '게시글 제목',
    summary      TEXT         COMMENT '요약 내용',
    image_count  INT          NOT NULL DEFAULT 0 COMMENT '이미지 수',
    post_date    DATETIME     COMMENT '게시글 원본 업로드 일시',
    status       ENUM('SUCCESS', 'FAIL') NOT NULL DEFAULT 'SUCCESS' COMMENT '처리 결과',
    UNIQUE KEY uk_board_post (board_id, post_id),
    INDEX idx_status (status),
    INDEX idx_reg_ts (reg_ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
