"""공지사항 처리에서 Google Photos 업로드 제거 회귀 테스트."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# playwright가 설치되지 않은 환경에서도 src.batch import 가능하도록 mock
if "playwright" not in sys.modules:
    sys.modules["playwright"] = MagicMock()
    sys.modules["playwright.async_api"] = MagicMock()

from src import batch as batch_module
from src.batch import _process_notice_board


@pytest.mark.asyncio
async def test_notice_images_are_analyzed_without_google_photos_upload() -> None:
    """공지 이미지는 분석/전송/DB 저장하되 Google Photos 경로를 사용하지 않는다."""
    context = MagicMock()
    last_seen = {"menus/6": 100}
    article = {"post_id": 101, "title": "이미지 공지", "url": "https://cafe/post/101"}
    image_url = "https://phinf.pstatic.net/example.JPEG?type=w800"
    paths = [Path("notice-101.jpg")]

    kakao = MagicMock()
    summarizer = MagicMock()
    summarizer.analyze_image.return_value = "분석 결과"
    repo = MagicMock()

    with (
        patch.object(batch_module, "_fetch_new_articles", new=AsyncMock(return_value=[article])),
        patch.object(
            batch_module,
            "_fetch_post_detail",
            new=AsyncMock(return_value={"images": [image_url], "text": "본문"}),
        ),
        patch.object(batch_module, "ImageDownloader") as downloader_cls,
        patch.object(batch_module, "GooglePhotosClient", create=True) as gphotos_cls,
    ):
        downloader_cls.return_value.download_all = AsyncMock(return_value=paths)

        await _process_notice_board(context, last_seen, kakao, summarizer, repo)

    gphotos_cls.assert_not_called()
    downloader_cls.return_value.download_all.assert_awaited_once_with(
        "101", [image_url.split("?")[0]]
    )
    summarizer.analyze_image.assert_called_once_with(paths[0])
    kakao.send_notice_summary.assert_called_once_with(
        "이미지 공지", "분석 결과", post_url="https://cafe/post/101"
    )
    repo.save.assert_called_once_with(
        board_id="menus/6",
        post_id=101,
        title="이미지 공지",
        summary="분석 결과",
        image_count=1,
        status="SUCCESS",
    )
    assert last_seen["menus/6"] == 101


@pytest.mark.asyncio
async def test_notice_processing_retries_then_saves_success() -> None:
    """공지 처리 일시 실패는 재시도하고 최종 성공 이력을 저장한다."""
    context = MagicMock()
    last_seen = {"menus/6": 100}
    article = {"post_id": 101, "title": "재시도 공지", "url": "https://cafe/post/101"}
    image_url = "https://phinf.pstatic.net/retry.JPEG?type=w800"
    paths = [Path("retry-101.jpg")]

    kakao = MagicMock()
    summarizer = MagicMock()
    summarizer.analyze_image.side_effect = [RuntimeError("분석 일시 실패"), "재시도 성공"]
    repo = MagicMock()

    with (
        patch.object(batch_module, "_fetch_new_articles", new=AsyncMock(return_value=[article])),
        patch.object(
            batch_module,
            "_fetch_post_detail",
            new=AsyncMock(return_value={"images": [image_url], "text": "본문"}),
        ) as fetch_detail,
        patch.object(batch_module, "ImageDownloader") as downloader_cls,
        patch.object(batch_module.asyncio, "sleep", new=AsyncMock()) as sleep,
    ):
        downloader_cls.return_value.download_all = AsyncMock(return_value=paths)

        await _process_notice_board(context, last_seen, kakao, summarizer, repo)

    assert fetch_detail.await_count == 2
    assert downloader_cls.return_value.download_all.await_count == 2
    assert sleep.await_count == 1
    kakao.send_notice_summary.assert_called_once_with(
        "재시도 공지", "재시도 성공", post_url="https://cafe/post/101"
    )
    repo.save.assert_called_once_with(
        board_id="menus/6",
        post_id=101,
        title="재시도 공지",
        summary="재시도 성공",
        image_count=1,
        status="SUCCESS",
    )
    assert last_seen["menus/6"] == 101


@pytest.mark.asyncio
async def test_notice_final_failure_is_saved_and_next_article_continues() -> None:
    """재시도 후 최종 실패한 공지는 FAIL로 저장하고 다음 공지는 계속 처리한다."""
    context = MagicMock()
    last_seen = {"menus/6": 100}
    articles = [
        {"post_id": 101, "title": "실패 공지", "url": "https://cafe/post/101"},
        {"post_id": 102, "title": "다음 공지", "url": "https://cafe/post/102"},
    ]

    kakao = MagicMock()
    summarizer = MagicMock()
    repo = MagicMock()

    fetch_detail = AsyncMock(
        side_effect=[
            RuntimeError("상세 조회 실패"),
            RuntimeError("상세 조회 실패"),
            RuntimeError("상세 조회 실패"),
            RuntimeError("상세 조회 실패"),
            {"images": [], "text": ""},
        ]
    )

    with (
        patch.object(batch_module, "_fetch_new_articles", new=AsyncMock(return_value=articles)),
        patch.object(batch_module, "_fetch_post_detail", new=fetch_detail),
        patch.object(batch_module, "ImageDownloader"),
        patch.object(batch_module.asyncio, "sleep", new=AsyncMock()) as sleep,
    ):
        await _process_notice_board(context, last_seen, kakao, summarizer, repo)

    assert sleep.await_count == 3
    assert repo.save.call_count == 2
    repo.save.assert_any_call(
        board_id="menus/6",
        post_id=101,
        title="실패 공지",
        summary="처리 실패 단계: detail_fetch\n오류: 상세 조회 실패",
        image_count=0,
        status="FAIL",
    )
    repo.save.assert_any_call(
        board_id="menus/6",
        post_id=102,
        title="다음 공지",
        summary=None,
        image_count=0,
        status="SUCCESS",
    )
    kakao.send_text.assert_called_once_with("[세화유치원 공지]\n\n📋 다음 공지")
    assert last_seen["menus/6"] == 102


@pytest.mark.asyncio
async def test_notice_final_failure_advances_last_seen() -> None:
    """최종 실패한 최신 공지도 처리된 이력으로 보고 커서를 전진한다."""
    context = MagicMock()
    last_seen = {"menus/6": 100}
    article = {"post_id": 101, "title": "최신 실패 공지", "url": "https://cafe/post/101"}
    kakao = MagicMock()
    summarizer = MagicMock()
    repo = MagicMock()

    with (
        patch.object(batch_module, "_fetch_new_articles", new=AsyncMock(return_value=[article])),
        patch.object(
            batch_module,
            "_fetch_post_detail",
            new=AsyncMock(side_effect=RuntimeError("상세 조회 실패")),
        ),
        patch.object(batch_module, "ImageDownloader"),
        patch.object(batch_module.asyncio, "sleep", new=AsyncMock()),
    ):
        await _process_notice_board(context, last_seen, kakao, summarizer, repo)

    repo.save.assert_called_once_with(
        board_id="menus/6",
        post_id=101,
        title="최신 실패 공지",
        summary="처리 실패 단계: detail_fetch\n오류: 상세 조회 실패",
        image_count=0,
        status="FAIL",
    )
    assert last_seen["menus/6"] == 101


@pytest.mark.asyncio
async def test_notice_empty_download_result_is_retried_and_saved_fail() -> None:
    """이미지 URL이 있는데 다운로드 결과가 0장이면 실패 이력으로 남긴다."""
    context = MagicMock()
    last_seen = {"menus/6": 100}
    article = {"post_id": 101, "title": "다운로드 실패 공지", "url": "https://cafe/post/101"}
    image_url = "https://phinf.pstatic.net/fail.JPEG?type=w800"
    kakao = MagicMock()
    summarizer = MagicMock()
    repo = MagicMock()

    with (
        patch.object(batch_module, "_fetch_new_articles", new=AsyncMock(return_value=[article])),
        patch.object(
            batch_module,
            "_fetch_post_detail",
            new=AsyncMock(return_value={"images": [image_url], "text": "본문"}),
        ),
        patch.object(batch_module, "ImageDownloader") as downloader_cls,
        patch.object(batch_module.asyncio, "sleep", new=AsyncMock()) as sleep,
    ):
        downloader_cls.return_value.download_all = AsyncMock(return_value=[])

        await _process_notice_board(context, last_seen, kakao, summarizer, repo)

    assert sleep.await_count == 3
    kakao.send_notice_summary.assert_not_called()
    summarizer.analyze_image.assert_not_called()
    repo.save.assert_called_once_with(
        board_id="menus/6",
        post_id=101,
        title="다운로드 실패 공지",
        summary="처리 실패 단계: image_download\n오류: 다운로드 성공 이미지 0/1장",
        image_count=0,
        status="FAIL",
    )
    assert last_seen["menus/6"] == 101


@pytest.mark.asyncio
async def test_notice_success_db_save_failure_is_retried() -> None:
    """성공 이력 DB 저장 실패는 외부 전송 없이 DB 저장만 재시도한다."""
    context = MagicMock()
    last_seen = {"menus/6": 100}
    article = {"post_id": 101, "title": "DB 재시도 공지", "url": "https://cafe/post/101"}
    kakao = MagicMock()
    summarizer = MagicMock()
    repo = MagicMock()
    repo.save.side_effect = [RuntimeError("DB 일시 실패"), None]

    with (
        patch.object(batch_module, "_fetch_new_articles", new=AsyncMock(return_value=[article])),
        patch.object(
            batch_module,
            "_fetch_post_detail",
            new=AsyncMock(return_value={"images": [], "text": ""}),
        ) as fetch_detail,
        patch.object(batch_module, "ImageDownloader"),
        patch.object(batch_module.asyncio, "sleep", new=AsyncMock()) as sleep,
    ):
        await _process_notice_board(context, last_seen, kakao, summarizer, repo)

    assert fetch_detail.await_count == 1
    assert sleep.await_count == 1
    assert repo.save.call_count == 2
    kakao.send_text.assert_called_once_with("[세화유치원 공지]\n\n📋 DB 재시도 공지")
    assert last_seen["menus/6"] == 101


@pytest.mark.asyncio
async def test_notice_success_db_save_exhaustion_does_not_resend_or_advance() -> None:
    """성공 이력 저장 재시도 소진 시 카카오 중복 전송 없이 커서를 보존한다."""
    context = MagicMock()
    last_seen = {"menus/6": 100}
    article = {"post_id": 101, "title": "DB 실패 공지", "url": "https://cafe/post/101"}
    kakao = MagicMock()
    summarizer = MagicMock()
    repo = MagicMock()
    repo.save.side_effect = RuntimeError("DB 지속 실패")

    with (
        patch.object(batch_module, "_fetch_new_articles", new=AsyncMock(return_value=[article])),
        patch.object(
            batch_module,
            "_fetch_post_detail",
            new=AsyncMock(return_value={"images": [], "text": ""}),
        ) as fetch_detail,
        patch.object(batch_module, "ImageDownloader"),
        patch.object(batch_module.asyncio, "sleep", new=AsyncMock()) as sleep,
    ):
        await _process_notice_board(context, last_seen, kakao, summarizer, repo)

    assert fetch_detail.await_count == 1
    assert sleep.await_count == 3
    assert repo.save.call_count == 4
    kakao.send_text.assert_called_once_with("[세화유치원 공지]\n\n📋 DB 실패 공지")
    assert last_seen["menus/6"] == 100


@pytest.mark.asyncio
async def test_notice_fail_db_save_failure_does_not_advance_last_seen() -> None:
    """FAIL 이력 저장까지 실패하면 어드민 확인이 불가하므로 커서를 전진하지 않는다."""
    context = MagicMock()
    last_seen = {"menus/6": 100}
    article = {"post_id": 101, "title": "저장 실패 공지", "url": "https://cafe/post/101"}
    kakao = MagicMock()
    summarizer = MagicMock()
    repo = MagicMock()
    repo.save.side_effect = RuntimeError("DB 저장 실패")

    with (
        patch.object(batch_module, "_fetch_new_articles", new=AsyncMock(return_value=[article])),
        patch.object(
            batch_module,
            "_fetch_post_detail",
            new=AsyncMock(side_effect=RuntimeError("상세 조회 실패")),
        ),
        patch.object(batch_module, "ImageDownloader"),
        patch.object(batch_module.asyncio, "sleep", new=AsyncMock()),
    ):
        await _process_notice_board(context, last_seen, kakao, summarizer, repo)

    assert repo.save.call_count == 4
    assert last_seen["menus/6"] == 100


@pytest.mark.asyncio
async def test_notice_fail_db_save_failure_stops_later_cursor_advance() -> None:
    """FAIL 저장 실패 뒤 다음 공지가 성공해도 실패 공지를 건너뛰지 않는다."""
    context = MagicMock()
    last_seen = {"menus/6": 100}
    articles = [
        {"post_id": 101, "title": "저장 실패 공지", "url": "https://cafe/post/101"},
        {"post_id": 102, "title": "다음 공지", "url": "https://cafe/post/102"},
    ]
    kakao = MagicMock()
    summarizer = MagicMock()
    repo = MagicMock()
    repo.save.side_effect = RuntimeError("DB 저장 실패")

    with (
        patch.object(batch_module, "_fetch_new_articles", new=AsyncMock(return_value=articles)),
        patch.object(
            batch_module,
            "_fetch_post_detail",
            new=AsyncMock(side_effect=RuntimeError("상세 조회 실패")),
        ) as fetch_detail,
        patch.object(batch_module, "ImageDownloader"),
        patch.object(batch_module.asyncio, "sleep", new=AsyncMock()),
    ):
        await _process_notice_board(context, last_seen, kakao, summarizer, repo)

    assert fetch_detail.await_count == 4
    assert repo.save.call_count == 4
    kakao.send_text.assert_not_called()
    assert last_seen["menus/6"] == 100


def test_batch_module_no_longer_imports_google_photos_client() -> None:
    """배치 시작 경로가 Google Photos 토큰 파일에 의존하지 않는다."""
    assert not hasattr(batch_module, "GooglePhotosClient")
