"""Google Photos 업로드 모듈.

access_token 자동 갱신, 이미지 업로드, 앨범 관리를 담당한다.
토큰은 config/google_token.json에서 로딩하고 갱신 시 동일 파일에 저장한다.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TOKEN_PATH = _REPO_ROOT / "config" / "google_token.json"

_TOKEN_URI = "https://oauth2.googleapis.com/token"
_UPLOAD_URL = "https://photoslibrary.googleapis.com/v1/uploads"
_BATCH_CREATE_URL = "https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate"
_ALBUMS_URL = "https://photoslibrary.googleapis.com/v1/albums"


def _sanitize_filename(name: str) -> str:
    """파일명에서 비ASCII 문자를 제거한다 (Google Photos 업로드 요구사항)."""
    return re.sub(r"[^\x00-\x7F]", "_", name)


class GooglePhotosClient:
    """Google Photos API 클라이언트.

    토큰 로딩, 자동 갱신, 이미지 업로드, 앨범 관리를 수행한다.
    """

    def __init__(self, token_path: Path = _DEFAULT_TOKEN_PATH) -> None:
        self._token_path = token_path
        self._token_data: dict = {}
        self._access_token: str = ""
        self._load_token()

    def _load_token(self) -> None:
        """토큰 파일을 로딩한다."""
        if not self._token_path.exists():
            raise FileNotFoundError(f"토큰 파일 없음: {self._token_path}")
        self._token_data = json.loads(
            self._token_path.read_text(encoding="utf-8")
        )
        self._access_token = self._token_data.get("token", "")
        logger.info("Google Photos 토큰 로딩 완료")

    def _save_token(self) -> None:
        """갱신된 토큰을 파일에 저장한다."""
        self._token_path.write_text(
            json.dumps(self._token_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Google Photos 토큰 저장 완료")

    def refresh_access_token(self) -> str:
        """refresh_token으로 access_token을 갱신한다."""
        refresh_token = self._token_data.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("refresh_token이 없습니다.")

        client_id = self._token_data.get("client_id", "")
        client_secret = self._token_data.get("client_secret", "")

        resp = requests.post(
            self._token_data.get("token_uri", _TOKEN_URI),
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"토큰 갱신 실패: {resp.status_code} {resp.text}")

        result = resp.json()
        self._access_token = result["access_token"]
        self._token_data["token"] = self._access_token

        # refresh_token이 새로 발급되면 업데이트
        if "refresh_token" in result:
            self._token_data["refresh_token"] = result["refresh_token"]

        self._save_token()
        logger.info("access_token 갱신 완료")
        return self._access_token

    def _ensure_valid_token(self) -> str:
        """유효한 access_token을 반환한다. 만료 시 자동 갱신."""
        # 간단한 테스트 요청으로 유효성 확인
        resp = requests.get(
            _ALBUMS_URL,
            headers={"Authorization": f"Bearer {self._access_token}"},
            params={"pageSize": 1},
            timeout=15,
        )
        if resp.status_code == 401:
            logger.info("access_token 만료, 갱신 중...")
            return self.refresh_access_token()
        return self._access_token

    def _auth_headers(self) -> dict[str, str]:
        """인증 헤더를 반환한다."""
        token = self._ensure_valid_token()
        return {"Authorization": f"Bearer {token}"}

    # ── 이미지 업로드 ────────────────────────────────────────────────────────

    def upload_images(self, image_paths: list[Path]) -> list[str]:
        """이미지를 Google Photos에 업로드하고 업로드 토큰 목록을 반환한다."""
        upload_tokens: list[str] = []
        headers = self._auth_headers()

        for path in image_paths:
            safe_name = _sanitize_filename(path.name)
            upload_headers = {
                **headers,
                "Content-Type": "application/octet-stream",
                "X-Goog-Upload-Protocol": "raw",
                "X-Goog-Upload-File-Name": safe_name,
            }
            with open(path, "rb") as f:
                resp = requests.post(
                    _UPLOAD_URL, headers=upload_headers, data=f, timeout=60
                )
            if resp.status_code != 200:
                logger.warning("업로드 실패: %s — %s %s", path.name, resp.status_code, resp.text)
                continue

            upload_tokens.append(resp.text)
            logger.info("업로드 완료: %s", path.name)

        return upload_tokens

    # ── 앨범 관리 ────────────────────────────────────────────────────────────

    def add_to_album(self, album_id: str, upload_tokens: list[str]) -> None:
        """업로드 토큰들을 앨범에 추가한다."""
        if not upload_tokens:
            return

        headers = {**self._auth_headers(), "Content-Type": "application/json"}
        body = {
            "albumId": album_id,
            "newMediaItems": [
                {
                    "simpleMediaItem": {"uploadToken": token}
                }
                for token in upload_tokens
            ],
        }
        resp = requests.post(
            _BATCH_CREATE_URL, headers=headers, json=body, timeout=30
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"앨범 추가 실패: {resp.status_code} {resp.text}"
            )
        logger.info("앨범에 %d장 추가 완료 (album_id=%s)", len(upload_tokens), album_id)

    def get_or_create_album(self, title: str) -> str:
        """제목으로 앨범을 검색하고, 없으면 생성하여 ID를 반환한다."""
        headers = self._auth_headers()

        # 기존 앨범 검색
        next_page = None
        while True:
            params: dict[str, str | int] = {"pageSize": 50}
            if next_page:
                params["pageToken"] = next_page
            resp = requests.get(
                _ALBUMS_URL, headers=headers, params=params, timeout=15
            )
            if resp.status_code != 200:
                break
            data = resp.json()
            for album in data.get("albums", []):
                if album.get("title") == title:
                    logger.info("기존 앨범 발견: %s (id=%s)", title, album["id"])
                    return album["id"]
            next_page = data.get("nextPageToken")
            if not next_page:
                break

        # 앨범 생성
        create_headers = {**headers, "Content-Type": "application/json"}
        resp = requests.post(
            _ALBUMS_URL,
            headers=create_headers,
            json={"album": {"title": title}},
            timeout=15,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"앨범 생성 실패: {resp.status_code} {resp.text}")
        album_id = resp.json()["id"]
        logger.info("새 앨범 생성: %s (id=%s)", title, album_id)
        return album_id
