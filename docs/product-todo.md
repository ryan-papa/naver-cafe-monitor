# Product · 기능 TODO

하네스 규칙이 아닌 **제품 기능** 추가 아이디어 목록. 각 항목은 정식 착수 시 `rp-workflow` 로 구체화 → PRD → 태스크 분해.

| # | 기능 | 메모 |
|:-:|------|------|
| 1 | 상세 모달에 이미지 리스트 표시 + 다운로드 | 현재는 `image_count` 만 노출. 원본 이미지 URL 을 DB(posts 에 JSON 추가 또는 별도 테이블)에 함께 저장. 모달에서 썸네일 그리드 + 개별/일괄 다운로드. |
| 2 | 공지사항 요약에서 일정 리스트업 | `menus/6` (공지) 요약 단계에서 `[일정 정리]` 블록을 파서로 추출 → `post_events` 테이블에 (date, target, description) 형태로 정규화 저장. 기능 3 의 전제. |
| 3 | 일정 전날 카카오톡 알림 | `post_events` 에서 내일자 이벤트를 찾아 하루 1회 카카오톡 발송 (batch cron). 전제: 기능 2 의 일정 추출 정확도 검증. |
| 4 | 카카오톡 오픈채팅 연동 (개인 메시지 대신) | 현재는 본인 계정 대상 "나에게 보내기". 오픈채팅방에 봇으로 메시지 포스팅. 카카오 채널 API / 비공식 (웹 자동화) / 외부 브릿지(Make, Zapier) 등 경로 검토 필요. 공식 API 가 오픈채팅 쓰기 지원 안 하면 실현 난이도 높음 — 사전 조사 항목. |
| 5 | 게시판 설정의 DB 화 + 관리자 UI | 현재 `config.yaml` 에 `menus/13`(사진)·`menus/6`(공지) 하드코딩. 이를 `boards` 테이블로 이전해 런타임 설정·관리자 UI로 CRUD. 컬럼 예: `board_id`(PK), `name`, `kind`(photo/notice/custom), `analysis_pipeline`(enum 또는 JSON: face_filter/llm_split/llm_summary), `output_channels`(JSON: kakao/gphotos/email), `prompt_template`, `active`. 배치는 active 한 board 전체를 순회하도록 변경. 새 게시판 추가 시 코드 배포 없이 대응 가능. |
