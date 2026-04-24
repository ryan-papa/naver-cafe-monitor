"""카카오 OAuth 토큰 관리 모듈.

access_token 자동 갱신, refresh_token 만료 알림을 담당한다.
토큰은 config/kakao_token.json에서 로딩하고 갱신 시 동일 파일에 저장한다.
refresh cron과 batch 프로세스의 교차 실행을 막기 위해 fcntl 파일 락 + 디스크 재로드·머지를 수행한다.
"""
from __future__ import annotations

import fcntl
import json
import logging
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TOKEN_PATH = _REPO_ROOT / "config" / "kakao_token.json"
_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
_KST = timezone(timedelta(hours=9))
_ALERT_DAYS_BEFORE = 14

# 락 획득 시 디스크에서 재로드·머지되는 볼러틸 필드 화이트리스트.
# 이 외 필드는 디스크 값 유지 (cron·batch 교차 실행 시 rotation 보존).
_VOLATILE_FIELDS = (
    "access_token",
    "expires_at",
    "refresh_token",
    "refresh_token_expires_at",
    "last_alert_date",
)


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
        self._lock_path = token_path.with_suffix(token_path.suffix + ".lock")
        self._token_data: dict = {}
        self._access_token: str = ""
        self._load_token()

    @contextmanager
    def _file_lock(self):
        """sidecar 락파일에 LOCK_EX 획득. 프로세스 간 직렬화."""
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = open(self._lock_path, "w")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            fd.close()

    def _read_disk(self) -> dict:
        """디스크에서 토큰 파일을 파싱해 반환한다."""
        raw = self._token_path.read_text(encoding="utf-8").strip()
        if not raw:
            raise InvalidTokenFile(f"카카오 토큰 파일이 비어 있습니다: {self._token_path}")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise InvalidTokenFile(
                f"카카오 토큰 파일 JSON 파싱 실패: {self._token_path} — {e}"
            ) from e

    def _load_token(self) -> None:
        """토큰 파일을 로딩한다 (초기화 전용)."""
        if not self._token_path.exists():
            raise FileNotFoundError(f"카카오 토큰 파일 없음: {self._token_path}")

        self._token_data = self._read_disk()

        required = ("access_token", "refresh_token")
        missing = [k for k in required if not self._token_data.get(k)]
        if missing:
            raise InvalidTokenFile(
                f"카카오 토큰 파일에 필수 필드 누락: {', '.join(missing)}"
            )

        self._access_token = self._token_data["access_token"]
        logger.info("카카오 토큰 로딩 완료")

    def _atomic_write(self, data: dict) -> None:
        """임시 파일 + rename 으로 atomic write."""
        content = json.dumps(data, ensure_ascii=False, indent=2)
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

    def _save_token(self) -> None:
        """현재 메모리의 볼러틸 필드를 락과 함께 저장한다 (하위 호환 엔트리)."""
        changes = {k: v for k, v in self._token_data.items() if k in _VOLATILE_FIELDS}
        self._commit_changes(changes)

    def _commit_changes(self, changes: dict) -> None:
        """락 획득 → 디스크 재로드 → 변경만 머지 → atomic write → 락 해제.

        다른 프로세스가 이미 쓴 필드를 보존하기 위해, 메모리 전체가 아닌 `changes` 딕셔너리만 덮어쓴다.
        `changes` 키는 `_VOLATILE_FIELDS` 에 속해야 한다.
        """
        invalid = [k for k in changes if k not in _VOLATILE_FIELDS]
        if invalid:
            raise ValueError(f"볼러틸 필드 화이트리스트 위반: {invalid}")

        with self._file_lock():
            try:
                disk = self._read_disk()
            except FileNotFoundError:
                disk = dict(self._token_data)
            disk.update(changes)
            self._atomic_write(disk)
            self._token_data = disk
            self._access_token = disk.get("access_token", self._access_token)
        logger.info("카카오 토큰 저장 완료")

    @property
    def access_token(self) -> str:
        return self._access_token

    def refresh(self) -> str:
        """refresh_token으로 access_token을 갱신한다.

        락 획득 후 디스크 최신 refresh_token 을 사용해 호출한다
        (다른 프로세스가 먼저 회전했을 경우 재사용 오류 방지).
        """
        with self._file_lock():
            try:
                disk = self._read_disk()
            except FileNotFoundError:
                disk = dict(self._token_data)
            refresh_token = disk.get("refresh_token")
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
                masked = _mask_tokens(resp.text)
                logger.error("카카오 토큰 갱신 실패: %s %s", resp.status_code, masked)
                raise RuntimeError(
                    f"카카오 토큰 갱신 실패: {resp.status_code} {masked}"
                )

            result = resp.json()
            now = int(time.time())
            changes: dict = {
                "access_token": result["access_token"],
                "expires_at": now + result.get("expires_in", 21599),
            }
            if "refresh_token" in result:
                changes["refresh_token"] = result["refresh_token"]
                if "refresh_token_expires_in" in result:
                    changes["refresh_token_expires_at"] = now + result["refresh_token_expires_in"]

            disk.update(changes)
            self._atomic_write(disk)
            self._token_data = disk
            self._access_token = disk["access_token"]

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
        self._commit_changes({"last_alert_date": today})


def _mask_tokens(body: str) -> str:
    """응답 본문에서 access_token / refresh_token 값을 `***` 로 치환.

    JSON 파싱 실패 시 정규식 fallback.
    """
    try:
        obj = json.loads(body)
        if isinstance(obj, dict):
            for k in ("access_token", "refresh_token"):
                if k in obj:
                    obj[k] = "***"
            return json.dumps(obj, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        pass

    import re
    return re.sub(
        r'"(access_token|refresh_token)"\s*:\s*"[^"]*"',
        r'"\1": "***"',
        body,
    )
