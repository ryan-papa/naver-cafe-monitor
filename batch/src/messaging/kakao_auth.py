"""카카오 OAuth 토큰 관리 모듈.

access_token 자동 갱신, refresh_token 만료 알림을 담당한다.
토큰은 config/kakao_token.json에서 로딩하고 갱신 시 동일 파일에 저장한다.
"""
from __future__ import annotations

import json
import logging
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TOKEN_PATH = _REPO_ROOT / "config" / "kakao_token.json"
_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
_KST = timezone(timedelta(hours=9))
_ALERT_DAYS_BEFORE = 14


class InvalidTokenFile(Exception):
    """토큰 파일이 손상되었거나 유효하지 않을 때 발생."""


class KakaoAuth:
    """카카오 OAuth 토큰 로드/저장/갱신을 담당한다."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_path: Path = _DEFAULT_TOKEN_PATH,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_path = token_path
        self._token_data: dict = {}
        self._access_token: str = ""
        self._load_token()

    def _load_token(self) -> None:
        """토큰 파일을 로딩한다."""
        if not self._token_path.exists():
            raise FileNotFoundError(f"카카오 토큰 파일 없음: {self._token_path}")

        raw = self._token_path.read_text(encoding="utf-8").strip()
        if not raw:
            raise InvalidTokenFile(f"카카오 토큰 파일이 비어 있습니다: {self._token_path}")

        try:
            self._token_data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise InvalidTokenFile(
                f"카카오 토큰 파일 JSON 파싱 실패: {self._token_path} — {e}"
            ) from e

        required = ("access_token", "refresh_token")
        missing = [k for k in required if not self._token_data.get(k)]
        if missing:
            raise InvalidTokenFile(
                f"카카오 토큰 파일에 필수 필드 누락: {', '.join(missing)}"
            )

        self._access_token = self._token_data["access_token"]
        logger.info("카카오 토큰 로딩 완료")

    def _save_token(self) -> None:
        """토큰을 파일에 atomic write로 저장한다."""
        content = json.dumps(self._token_data, ensure_ascii=False, indent=2)
        # atomic write: 임시 파일에 쓴 뒤 rename
        parent = self._token_path.parent
        parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=parent, suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(content)
            Path(tmp_path).replace(self._token_path)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise
        logger.info("카카오 토큰 저장 완료")

    @property
    def access_token(self) -> str:
        return self._access_token

    def refresh(self) -> str:
        """refresh_token으로 access_token을 갱신한다."""
        refresh_token = self._token_data.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("refresh_token이 없습니다.")

        resp = requests.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": refresh_token,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            logger.error(
                "카카오 토큰 갱신 실패: %s %s", resp.status_code, resp.text
            )
            raise RuntimeError(
                f"카카오 토큰 갱신 실패: {resp.status_code} {resp.text}"
            )

        result = resp.json()
        self._access_token = result["access_token"]
        self._token_data["access_token"] = self._access_token
        self._token_data["expires_at"] = int(time.time()) + result.get("expires_in", 21599)

        # refresh_token이 새로 발급되면 업데이트, 없으면 기존 값 유지
        if "refresh_token" in result:
            self._token_data["refresh_token"] = result["refresh_token"]
            if "refresh_token_expires_in" in result:
                self._token_data["refresh_token_expires_at"] = (
                    int(time.time()) + result["refresh_token_expires_in"]
                )

        self._save_token()
        logger.info("카카오 access token 갱신 완료")
        return self._access_token

    def check_refresh_token_expiry(self) -> int | None:
        """refresh_token 만료까지 남은 일수를 반환한다. 알 수 없으면 None."""
        expires_at = self._token_data.get("refresh_token_expires_at")
        if not expires_at:
            return None
        remaining = int(expires_at) - int(time.time())
        return max(0, remaining // 86400)

    def should_alert_today(self) -> bool:
        """오늘 만료 알림을 보내야 하는지 판단한다."""
        days_left = self.check_refresh_token_expiry()
        if days_left is None or days_left > _ALERT_DAYS_BEFORE:
            return False

        today = datetime.now(_KST).strftime("%Y-%m-%d")
        last_alert = self._token_data.get("last_alert_date", "")
        return today != last_alert

    def mark_alert_sent(self) -> None:
        """오늘 알림을 보냈음을 기록한다."""
        today = datetime.now(_KST).strftime("%Y-%m-%d")
        self._token_data["last_alert_date"] = today
        self._save_token()
