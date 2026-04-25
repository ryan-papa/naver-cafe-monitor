## 기술 리스크 / Findings

1. **현재 구현은 PRD 목표와 정면으로 충돌함**
   - `batch/src/batch.py:27`에서 `GooglePhotosClient`를 import하고, `run()`에서 즉시 생성합니다(`batch/src/batch.py:300-301`).
   - `GooglePhotosClient.__init__()`는 `config/google_token.json` 부재 시 `FileNotFoundError`를 발생시킵니다(`batch/src/storage/google_photos.py:37-46`).
   - 따라서 PRD 성공 기준인 "토큰 파일 부재가 배치 시작 실패를 일으키지 않는다"는 현재 코드에서는 미충족입니다.

2. **공지 처리 경로가 아직 Google Photos 업로드 실패에 종속됨**
   - `_process_notice_board()` 시그니처가 `gphotos: GooglePhotosClient`를 필수 인자로 받습니다(`batch/src/batch.py:203-206`).
   - 이미지 다운로드 직후 `upload_images()`와 `add_to_album()`을 호출합니다(`batch/src/batch.py:237-240`).
   - 이 호출은 이미지 분석보다 먼저 실행되므로 Google Photos 장애가 공지 요약 전송까지 막을 수 있습니다.

3. **테스트 커버리지 보강이 필수**
   - PRD는 `_process_notice_board()`와 `run()` 단위 테스트를 요구하지만(`docs/prd/...md:81-82`), 현재 `batch/tests`에는 해당 직접 회귀 테스트가 없습니다.
   - 특히 `GooglePhotosClient` 미생성, `upload_images`/`add_to_album` 미호출, `analyze_image`/`send_notice_summary`/`repo.save` 유지 검증이 추가되어야 합니다.

4. **보안/운영 측면의 잔여 정리 범위가 다소 애매함**
   - PRD는 Google Photos 모듈 파일 삭제를 범위 밖으로 두는 판단은 적절합니다(`docs/prd/...md:16`, `:71`).
   - 다만 공지용 `_NOTICE_ALBUM_ID`, `_NOTICE_ALBUM_URL` 상수는 제거 대상에 포함할지 명시하면 시크릿/운영 혼선을 더 줄일 수 있습니다(`batch/src/batch.py:44-45`).

## 항목별 점수

| 항목 | 점수 | 근거 |
|---|---:|---|
| 아키텍처 | 8 | 공지 경로에서 Google Photos 의존성만 제거하는 최소 변경안은 현재 구조에 잘 맞습니다. 단, `run()` 초기화와 함수 시그니처 제거까지 명확히 구현되어야 합니다. |
| 확장성 | 8 | 외부 업로드 병목을 제거하므로 공지 이미지 처리량 증가에 유리합니다. 장기적으로는 게시판별 출력 채널 설정화와도 충돌하지 않습니다. |
| 보안 | 8 | Google 토큰 파일 의존성 제거는 시크릿 노출면을 줄입니다. 다만 공지 앨범 ID/URL 상수 잔존 처리 방침은 더 명확히 하는 편이 좋습니다. |
| 성능 | 9 | 이미지 공지 처리에서 Google Photos HTTP 업로드와 앨범 추가 호출이 빠지므로 지연과 실패 지점이 줄어듭니다. |
| 운영성 | 8 | 토큰 파일 누락으로 배치가 시작 실패하는 운영 리스크를 제거하는 방향이 타당합니다. 테스트가 추가되지 않으면 회귀 탐지가 약합니다. |

**평균:** 8.2

## 판정

**PASS**

평균 8.0 이상이고 모든 항목이 7점 이상입니다. 단, 개발 단계에서는 `batch/src/batch.py`의 `GooglePhotosClient` import/생성/공지 인자/업로드 호출 제거와 직접 단위 테스트 추가가 통과 조건입니다.

## 검증 메모

- 파일 수정 없음.
- Claude-only 명령 실행 없음.
- 테스트 실행 없음. 리뷰 범위에 따라 PRD, `batch/src/batch.py`, 관련 테스트 파일을 정적 확인했습니다.

## 반영

- 공지용 Google Photos 앨범 ID/URL 상수는 업로드 제거 후 사용처가 없어지므로 구현 범위에서 제거한다.
