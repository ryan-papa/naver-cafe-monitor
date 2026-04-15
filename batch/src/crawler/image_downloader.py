"""이미지 다운로더.

게시물 내 이미지 URL 목록을 받아 로컬에 다운로드한다.
중복 다운로드를 방지하고, 개별 실패는 스킵 후 로그 기록하며 전체 중단하지 않는다.
playwright 세션의 쿠키를 httpx에 전달할 수 있도록 설계되어 있다.
"""
from __future__ import annotations

import logging
import mimetypes
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = Path("data/images")
_DEFAULT_TIMEOUT = 30.0
_DEFAULT_CHUNK_SIZE = 8192


def _extract_filename(url: str, index: int, content_type: Optional[str] = None) -> str:
    """URL 또는 Content-Type으로부터 저장할 파일명을 결정한다."""
    parsed = urlparse(url)
    path_part = parsed.path.rstrip("/")
    name = path_part.split("/")[-1] if path_part else ""

    # 쿼리스트링만 있는 경우 등 이름이 없으면 index 기반 생성
    if not name or "." not in name:
        ext = ""
        if content_type:
            ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
            # mimetypes 가 .jpe 등을 반환할 수 있으므로 정규화
            ext = _normalize_ext(ext)
        name = f"image_{index:04d}{ext}"

    # 파일명에서 안전하지 않은 문자 제거
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name


def _normalize_ext(ext: str) -> str:
    """확장자를 일반적인 형태로 정규화한다."""
    mapping = {".jpe": ".jpg", ".jpeg": ".jpg"}
    return mapping.get(ext.lower(), ext.lower())


def _build_save_path(base_dir: Path, post_id: str, filename: str) -> Path:
    """저장 경로를 구성한다: base_dir/{post_id}/{filename}"""
    return base_dir / post_id / filename


class ImageDownloader:
    """게시물 이미지를 로컬 디렉터리에 비동기 다운로드하는 클래스.

    사용 예::

        downloader = ImageDownloader()
        paths = await downloader.download_all(
            post_id="12345",
            image_urls=["https://example.com/a.jpg"],
            cookies={"NID_AUT": "..."},
        )
    """

    def __init__(
        self,
        base_dir: Path = _DEFAULT_BASE_DIR,
        timeout: float = _DEFAULT_TIMEOUT,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
    ) -> None:
        self._base_dir = Path(base_dir)
        self._timeout = timeout
        self._chunk_size = chunk_size

    # ── 공개 API ──────────────────────────────────────────────────────────────

    async def download_all(
        self,
        post_id: str,
        image_urls: list[str],
        cookies: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> list[Path]:
        """이미지 URL 목록을 순서대로 다운로드하고 저장된 로컬 경로 목록을 반환한다.

        - 이미 존재하는 파일은 스킵한다.
        - 개별 이미지 다운로드 실패 시 해당 URL만 건너뛰고 계속 진행한다.

        Args:
            post_id: 게시물 ID (하위 디렉터리 이름으로 사용).
            image_urls: 다운로드할 이미지 URL 목록.
            cookies: playwright 세션 등에서 전달받은 쿠키 딕셔너리.
            headers: 추가 HTTP 헤더.

        Returns:
            성공적으로 저장된 로컬 파일 경로 목록.
        """
        if not image_urls:
            return []

        merged_headers = self._build_headers(headers)
        saved_paths: list[Path] = []

        async with httpx.AsyncClient(
            cookies=cookies or {},
            headers=merged_headers,
            timeout=self._timeout,
            follow_redirects=True,
        ) as client:
            for index, url in enumerate(image_urls):
                path = await self._download_one(client, post_id, url, index)
                if path is not None:
                    saved_paths.append(path)

        logger.info(
            "post_id=%s: %d/%d 이미지 다운로드 완료",
            post_id,
            len(saved_paths),
            len(image_urls),
        )
        return saved_paths

    # ── 내부 메서드 ───────────────────────────────────────────────────────────

    def _build_headers(self, extra: Optional[dict[str, str]]) -> dict[str, str]:
        """기본 헤더에 추가 헤더를 병합한다."""
        base = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://cafe.naver.com/",
        }
        if extra:
            base.update(extra)
        return base

    async def _download_one(
        self,
        client: httpx.AsyncClient,
        post_id: str,
        url: str,
        index: int,
    ) -> Optional[Path]:
        """단일 이미지를 다운로드한다. 실패 시 None 반환."""
        try:
            # HEAD 요청으로 Content-Type 파악 (지원하지 않는 서버는 GET으로 폴백)
            content_type: Optional[str] = None
            try:
                head_resp = await client.head(url)
                content_type = head_resp.headers.get("content-type")
            except Exception:
                pass

            filename = _extract_filename(url, index, content_type)
            save_path = _build_save_path(self._base_dir, post_id, filename)

            if save_path.exists():
                logger.debug("스킵(이미 존재): %s", save_path)
                return save_path

            # 실제 다운로드
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                # Content-Type이 HEAD에서 못 얻었을 때 GET 응답에서 재시도
                if content_type is None:
                    content_type = resp.headers.get("content-type")
                    filename = _extract_filename(url, index, content_type)
                    save_path = _build_save_path(self._base_dir, post_id, filename)

                save_path.parent.mkdir(parents=True, exist_ok=True)
                with save_path.open("wb") as fp:
                    async for chunk in resp.aiter_bytes(self._chunk_size):
                        fp.write(chunk)

            logger.debug("다운로드 완료: %s -> %s", url, save_path)
            return save_path

        except Exception as exc:
            logger.warning("다운로드 실패 (스킵): url=%s, error=%s", url, exc)
            return None
