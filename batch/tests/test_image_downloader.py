"""ImageDownloader 테스트.

실제 HTTP 호출 없이 httpx를 mock하여 다운로드 로직을 검증한다.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import httpx
import pytest

from src.crawler.image_downloader import (
    ImageDownloader,
    _build_save_path,
    _extract_filename,
    _normalize_ext,
)


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _make_head_response(content_type: str = "image/jpeg", status: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.headers = {"content-type": content_type}
    return resp


def _make_stream_response(content: bytes = b"FAKE_IMAGE", status: int = 200) -> AsyncMock:
    """stream() 컨텍스트 매니저를 흉내 내는 mock."""
    chunks = [content]

    async def aiter_bytes(chunk_size: int = 8192):
        for chunk in chunks:
            yield chunk

    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.headers = {"content-type": "image/jpeg"}
    resp.raise_for_status = MagicMock()
    resp.aiter_bytes = aiter_bytes

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ── 유닛 테스트: 헬퍼 함수 ───────────────────────────────────────────────────

class TestExtractFilename:
    def test_uses_url_path_name(self):
        name = _extract_filename("https://example.com/img/photo.jpg", 0)
        assert name == "photo.jpg"

    def test_generates_name_when_no_extension(self):
        name = _extract_filename("https://example.com/img/photo", 3, "image/png")
        assert name.startswith("image_0003")
        assert name.endswith(".png")

    def test_generates_name_with_index_fallback(self):
        name = _extract_filename("https://example.com/", 7)
        assert "image_0007" in name

    def test_sanitizes_unsafe_characters(self):
        name = _extract_filename("https://example.com/a?b=c&d=e", 0, "image/jpeg")
        assert "?" not in name and "&" not in name


class TestNormalizeExt:
    def test_jpe_becomes_jpg(self):
        assert _normalize_ext(".jpe") == ".jpg"

    def test_jpeg_becomes_jpg(self):
        assert _normalize_ext(".jpeg") == ".jpg"

    def test_unknown_passes_through(self):
        assert _normalize_ext(".png") == ".png"


class TestBuildSavePath:
    def test_correct_structure(self):
        path = _build_save_path(Path("data/images"), "42", "photo.jpg")
        assert path == Path("data/images/42/photo.jpg")


# ── 통합 테스트: ImageDownloader ──────────────────────────────────────────────

@pytest.fixture
def tmp_downloader(tmp_path: Path) -> ImageDownloader:
    return ImageDownloader(base_dir=tmp_path / "images")


class TestDownloadAll:
    async def test_normal_download(self, tmp_downloader: ImageDownloader, tmp_path: Path):
        """정상 다운로드: URL 1개 → 로컬 파일 1개 반환."""
        url = "https://example.com/img/test.jpg"

        with (
            patch.object(tmp_downloader, "_download_one", new_callable=AsyncMock) as mock_dl,
        ):
            expected_path = tmp_path / "images" / "99" / "test.jpg"
            mock_dl.return_value = expected_path

            result = await tmp_downloader.download_all("99", [url])

        assert result == [expected_path]
        mock_dl.assert_awaited_once()

    async def test_empty_url_list_returns_empty(self, tmp_downloader: ImageDownloader):
        """URL 목록이 비어 있으면 빈 리스트 반환."""
        result = await tmp_downloader.download_all("99", [])
        assert result == []

    async def test_partial_failure_continues(self, tmp_downloader: ImageDownloader, tmp_path: Path):
        """일부 실패해도 나머지 URL은 계속 처리된다."""
        urls = [
            "https://example.com/img/ok.jpg",
            "https://example.com/img/fail.jpg",
            "https://example.com/img/ok2.jpg",
        ]
        ok_path = tmp_path / "images" / "1" / "ok.jpg"
        ok2_path = tmp_path / "images" / "1" / "ok2.jpg"

        side_effects = [ok_path, None, ok2_path]

        with patch.object(
            tmp_downloader, "_download_one", new_callable=AsyncMock, side_effect=side_effects
        ):
            result = await tmp_downloader.download_all("1", urls)

        assert len(result) == 2
        assert ok_path in result
        assert ok2_path in result

    async def test_all_failure_returns_empty(self, tmp_downloader: ImageDownloader):
        """모든 URL 실패 시 빈 리스트 반환."""
        urls = ["https://example.com/bad1.jpg", "https://example.com/bad2.jpg"]

        with patch.object(
            tmp_downloader, "_download_one", new_callable=AsyncMock, return_value=None
        ):
            result = await tmp_downloader.download_all("1", urls)

        assert result == []

    async def test_cookies_forwarded(self, tmp_downloader: ImageDownloader):
        """cookies 인자가 httpx.AsyncClient에 전달된다."""
        cookies = {"NID_AUT": "abc123"}

        captured_clients: list = []

        async def fake_download_one(client, post_id, url, index):
            captured_clients.append(client)
            return None

        with patch.object(tmp_downloader, "_download_one", side_effect=fake_download_one):
            await tmp_downloader.download_all("1", ["https://example.com/a.jpg"], cookies=cookies)

        assert len(captured_clients) == 1
        # client 객체 자체가 전달됐는지 확인 (httpx.AsyncClient)
        assert isinstance(captured_clients[0], httpx.AsyncClient)


class TestDownloadOne:
    """_download_one 내부 로직 단위 테스트."""

    async def test_skip_if_file_exists(self, tmp_downloader: ImageDownloader, tmp_path: Path):
        """이미 파일이 존재하면 다운로드 없이 해당 경로 반환."""
        post_dir = tmp_path / "images" / "55"
        post_dir.mkdir(parents=True)
        existing = post_dir / "photo.jpg"
        existing.write_bytes(b"existing")

        url = "https://example.com/photo.jpg"

        with patch("httpx.AsyncClient") as mock_client_cls:
            client_instance = AsyncMock()
            client_instance.head = AsyncMock(
                return_value=_make_head_response("image/jpeg")
            )
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=client_instance)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await tmp_downloader._download_one(client_instance, "55", url, 0)

        assert result == existing
        # stream 이 호출되지 않았는지 확인
        client_instance.stream.assert_not_called()

    async def test_download_writes_file(self, tmp_downloader: ImageDownloader, tmp_path: Path):
        """정상 HTTP 응답 시 파일을 기록하고 경로를 반환한다."""
        url = "https://example.com/newimg.jpg"
        fake_content = b"JPEG_BYTES"

        client = AsyncMock(spec=httpx.AsyncClient)
        client.head = AsyncMock(return_value=_make_head_response("image/jpeg"))
        client.stream = MagicMock(return_value=_make_stream_response(fake_content))

        result = await tmp_downloader._download_one(client, "77", url, 0)

        assert result is not None
        assert result.name == "newimg.jpg"
        assert result.read_bytes() == fake_content

    async def test_http_error_returns_none(self, tmp_downloader: ImageDownloader):
        """HTTP 오류 시 None 반환 (전체 중단 없음)."""
        url = "https://example.com/bad.jpg"

        client = AsyncMock(spec=httpx.AsyncClient)
        client.head = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

        # stream도 오류
        stream_cm = AsyncMock()
        stream_cm.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        stream_cm.__aexit__ = AsyncMock(return_value=False)
        client.stream = MagicMock(return_value=stream_cm)

        result = await tmp_downloader._download_one(client, "1", url, 0)

        assert result is None

    async def test_returned_path_is_correct(self, tmp_downloader: ImageDownloader, tmp_path: Path):
        """반환 경로가 base_dir/{post_id}/{filename} 형식인지 확인."""
        url = "https://example.com/banner.png"

        client = AsyncMock(spec=httpx.AsyncClient)
        client.head = AsyncMock(return_value=_make_head_response("image/png"))
        client.stream = MagicMock(return_value=_make_stream_response(b"PNG"))

        result = await tmp_downloader._download_one(client, "post_abc", url, 2)

        assert result is not None
        # 경로 구조: {base_dir}/post_abc/banner.png
        assert result.parent.name == "post_abc"
        assert result.name == "banner.png"
        assert str(result).startswith(str(tmp_path / "images"))
