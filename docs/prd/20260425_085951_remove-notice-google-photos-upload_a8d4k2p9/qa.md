# QA: 공지사항 Google Photos 업로드 제거

**일시:** 2026-04-25
**대상:** `feat/remove-notice-google-photos-upload`

## 사전 검증

| 항목 | 결과 | 근거 |
|------|------|------|
| 태스크 완료 | Pass | T-61, T-62 Done |
| 기능 PRD 매핑 | Pass | F-01~F-05가 T-61/T-62에 매핑됨 |
| UI 변경 여부 | 해당 없음 | 배치 Python 코드 변경만 포함 |

## 기능 QA

| 시나리오 | 결과 | 근거 |
|----------|------|------|
| Google Photos 토큰 없이 배치 공지 경로가 import/초기화 가능 | Pass | `test_batch_module_no_longer_imports_google_photos_client` |
| 이미지 포함 공지에서 다운로드, 이미지 분석, 카카오 요약 전송, DB 저장 유지 | Pass | `test_notice_images_are_analyzed_without_google_photos_upload` |
| 공지 처리 경로의 Google Photos 업로드/앨범 추가 호출 제거 | Pass | `src.batch`에 `GooglePhotosClient` 속성 없음, 업로드 호출 제거 |
| 공지 처리 일시 실패 후 재시도 성공 | Pass | `test_notice_processing_retries_then_saves_success` |
| 재시도 후 최종 실패 시 `FAIL` DB 저장 및 다음 게시글 계속 처리 | Pass | `test_notice_final_failure_is_saved_and_next_article_continues` |
| 최종 실패한 최신 공지도 처리 커서 전진 | Pass | `test_notice_final_failure_advances_last_seen` |
| 이미지 URL이 있는데 다운로드 성공 0장이면 `image_download` 실패로 기록 | Pass | `test_notice_empty_download_result_is_retried_and_saved_fail` |
| 성공 이력 DB 저장 재시도 시 카카오 중복 전송 없음 | Pass | `test_notice_success_db_save_failure_is_retried` |
| 최종 FAIL 이력 저장 실패 시 커서 미전진 | Pass | `test_notice_fail_db_save_failure_does_not_advance_last_seen` |
| 최종 FAIL 이력 저장 실패 후 이후 공지 처리 중단 | Pass | `test_notice_fail_db_save_failure_stops_later_cursor_advance` |
| DB 기반 last_seen이 `FAIL` 이력도 처리 완료로 간주 | Pass | `test_post_tracker.py`, `test_post_repository.py` |
| 사진 게시판/카카오 메시징 회귀 | Pass | 전체 `batch/tests` 통과 |

## 실행 결과

```text
rtk pytest batch/tests/test_notice_google_photos_removed.py batch/tests/test_batch_alert.py -q
Pytest: 9 passed

rtk pytest batch/tests/test_notice_google_photos_removed.py -q
Pytest: 9 passed

rtk pytest batch/tests/test_notice_google_photos_removed.py batch/tests/test_post_tracker.py batch/tests/test_post_repository.py -q
Pytest: 30 passed

rtk pytest batch/tests api/tests/test_api.py -q
Pytest: 243 passed

rtk proxy python3 -m compileall batch/src/batch.py batch/src/crawler/post_tracker.py shared/post_repository.py batch/tests/test_notice_google_photos_removed.py
Compiling 'batch/src/batch.py'...
Compiling 'batch/tests/test_notice_google_photos_removed.py'...
```

## E2E / 접근성

해당 없음. 이번 변경은 UI 또는 웹 라우팅 변경이 아니며, 브라우저 렌더링과 axe 검증 대상이 없다.

## 사용자 검증 게이트

릴리스 전 운영 환경에서 `config/google_token.json` 없이 배치를 1회 실행하고, 이미지 포함 공지의 카카오 요약 수신과 DB 기록을 확인해야 한다. 현재 로컬 QA에서는 외부 네이버/카카오 운영 계정 실행을 수행하지 않았다.

## 판정

Pass. 코드 레벨 QA와 회귀 테스트 기준을 충족한다.
