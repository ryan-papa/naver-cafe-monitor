-- naver_cafe_monitor 초기 DDL
-- 실행: mysql -h <host> -u <user> -p <database> < db/ddl.sql
-- 스타일 가이드: ../../docs/harness-db.md

CREATE DATABASE IF NOT EXISTS naver_cafe_monitor
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE naver_cafe_monitor;

-- ─────────────────────────────────────────────────────────────
-- posts : 배치 크롤러의 게시글 처리 이력
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS posts (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY
                 COMMENT '자동 증가 PK',
    reg_ts       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                 COMMENT '레코드 생성 시각 (서버 로컬). 처리 완료 시점과 동일.',
    upd_ts       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                 COMMENT '레코드 갱신 시각. 재발송·상태 변경 시 자동 갱신.',
    board_id     VARCHAR(50)  NOT NULL
                 COMMENT '게시판 식별자. menus/13=사진게시판, menus/6=공지사항',
    post_id      BIGINT       NOT NULL
                 COMMENT '네이버 카페 게시글 번호 (게시판 내 unique).',
    title        VARCHAR(500) NOT NULL DEFAULT ''
                 COMMENT '게시글 제목 원문. 이모지 포함 가능.',
    summary      TEXT
                 COMMENT 'AI(Claude) 가 생성한 요약 본문. 카카오톡 발송 전문.',
    image_count  INT          NOT NULL DEFAULT 0
                 COMMENT '원본 게시글의 이미지 개수. 얼굴 필터링 전 기준.',
    post_date    DATETIME
                 COMMENT '게시글 원본 업로드 일시 (네이버 카페 표시값). 파싱 실패 시 NULL.',
    status       ENUM('SUCCESS', 'FAIL') NOT NULL DEFAULT 'SUCCESS'
                 COMMENT '처리 결과. '
                         'SUCCESS=전체 파이프라인 정상 완료 / '
                         'FAIL=크롤링·요약·발송 중 예외 발생',
    UNIQUE KEY uk_board_post (board_id, post_id)
                 COMMENT '(board, post) 조합으로 중복 처리 방지 — 배치 멱등성 핵심',
    INDEX     idx_status (status)
                 COMMENT '대시보드 성공/실패 카운트 집계용',
    INDEX     idx_reg_ts (reg_ts)
                 COMMENT '최신순 정렬·기간 필터 조회용'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='배치 크롤러의 게시글 처리 이력. 재발송·대시보드 소스.';
