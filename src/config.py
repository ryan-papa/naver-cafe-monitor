"""설정 관리 모듈.

config.yaml (없으면 config.example.yaml 폴백) + .env 기반으로 설정을 로딩한다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _PROJECT_ROOT / "config"

_REQUIRED_ENV_VARS = ("NAVER_ID", "NAVER_PW", "KAKAO_TOKEN", "ANTHROPIC_API_KEY")


@dataclass
class BoardConfig:
    id: int
    name: str
    face_check: bool = False


@dataclass
class FaceConfig:
    tolerance: float = 0.55
    reference_dir: str = "data/faces/"


@dataclass
class KakaoConfig:
    enabled: bool = True
    target_id: str = "me"


@dataclass
class NotificationConfig:
    kakao: KakaoConfig = field(default_factory=KakaoConfig)


@dataclass
class SummaryConfig:
    enabled: bool = True
    model: str = "claude-3-5-haiku-20241022"
    max_tokens: int = 300


class Config:
    """애플리케이션 전체 설정을 보관하고 접근 인터페이스를 제공한다."""

    def __init__(self, raw: dict[str, Any], env_vars: dict[str, str]) -> None:
        scheduler = raw.get("scheduler", {})
        self._poll_interval: int = int(scheduler.get("poll_interval_seconds", 300))
        self._timezone: str = scheduler.get("timezone", "Asia/Seoul")
        self._polling_enabled: bool = True

        cafe = raw.get("cafe", {})
        self._cafe_url: str = cafe.get("url", "")
        self._boards: list[BoardConfig] = [
            BoardConfig(
                id=b["id"],
                name=b["name"],
                face_check=b.get("face_check", False),
            )
            for b in cafe.get("boards", [])
        ]

        face_raw = raw.get("face", {})
        self._face = FaceConfig(
            tolerance=float(face_raw.get("tolerance", 0.55)),
            reference_dir=face_raw.get("reference_dir", "data/faces/"),
        )

        notif_raw = raw.get("notification", {})
        kakao_raw = notif_raw.get("kakao", {})
        self._notification = NotificationConfig(
            kakao=KakaoConfig(
                enabled=bool(kakao_raw.get("enabled", True)),
                target_id=str(kakao_raw.get("target_id", "me")),
            )
        )

        summary_raw = raw.get("summary", {})
        self._summary = SummaryConfig(
            enabled=bool(summary_raw.get("enabled", True)),
            model=str(summary_raw.get("model", "claude-3-5-haiku-20241022")),
            max_tokens=int(summary_raw.get("max_tokens", 300)),
        )

        retry_raw = raw.get("retry", {})
        self._retry_max: int = int(retry_raw.get("max_retries", 3))
        self._retry_delay: float = float(retry_raw.get("delay_seconds", 5))
        self._retry_exponential_backoff: bool = bool(
            retry_raw.get("exponential_backoff", False)
        )

        # 인증정보 — 환경변수에서만 로딩, 절대 하드코딩 금지
        self._naver_id: str = env_vars["NAVER_ID"]
        self._naver_pw: str = env_vars["NAVER_PW"]
        self._kakao_token: str = env_vars["KAKAO_TOKEN"]
        self._anthropic_api_key: str = env_vars["ANTHROPIC_API_KEY"]

    # ── 스케줄러 ──────────────────────────────────────────────────────────────

    @property
    def poll_interval(self) -> int:
        return self._poll_interval

    @property
    def timezone(self) -> str:
        return self._timezone

    @property
    def polling_enabled(self) -> bool:
        return self._polling_enabled

    # ── 폴링 ON/OFF 런타임 토글 ───────────────────────────────────────────────

    def enable_polling(self) -> None:
        """폴링을 활성화한다."""
        self._polling_enabled = True

    def disable_polling(self) -> None:
        """폴링을 비활성화한다."""
        self._polling_enabled = False

    def toggle_polling(self) -> bool:
        """폴링 상태를 반전하고 변경 후 상태를 반환한다."""
        self._polling_enabled = not self._polling_enabled
        return self._polling_enabled

    # ── 카페 ─────────────────────────────────────────────────────────────────

    @property
    def cafe_url(self) -> str:
        return self._cafe_url

    @property
    def boards(self) -> list[BoardConfig]:
        return self._boards

    # ── 얼굴 인식 ─────────────────────────────────────────────────────────────

    @property
    def face(self) -> FaceConfig:
        return self._face

    # ── 알림 ─────────────────────────────────────────────────────────────────

    @property
    def notification(self) -> NotificationConfig:
        return self._notification

    # ── 요약 ─────────────────────────────────────────────────────────────────

    @property
    def summary(self) -> SummaryConfig:
        return self._summary

    # ── 재시도 ───────────────────────────────────────────────────────────────

    @property
    def retry_max(self) -> int:
        return self._retry_max

    @property
    def retry_delay(self) -> float:
        return self._retry_delay

    @property
    def retry_exponential_backoff(self) -> bool:
        return self._retry_exponential_backoff

    # ── 인증정보 ──────────────────────────────────────────────────────────────

    @property
    def naver_id(self) -> str:
        return self._naver_id

    @property
    def naver_pw(self) -> str:
        return self._naver_pw

    @property
    def kakao_token(self) -> str:
        return self._kakao_token

    @property
    def anthropic_api_key(self) -> str:
        return self._anthropic_api_key


def _load_yaml(config_dir: Path) -> dict[str, Any]:
    """config.yaml 또는 config.example.yaml을 로딩한다."""
    primary = config_dir / "config.yaml"
    fallback = config_dir / "config.example.yaml"

    if primary.exists():
        path = primary
    elif fallback.exists():
        path = fallback
    else:
        raise FileNotFoundError(
            f"설정 파일을 찾을 수 없습니다: {primary} 또는 {fallback}"
        )

    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_env_vars(env_file: Path | None = None) -> dict[str, str]:
    """환경변수를 로딩하고 필수 키가 모두 있는지 검증한다."""
    dotenv_path = env_file or (_PROJECT_ROOT / ".env")
    load_dotenv(dotenv_path=dotenv_path, override=False)

    missing = [key for key in _REQUIRED_ENV_VARS if not os.getenv(key)]
    if missing:
        raise EnvironmentError(
            f"필수 환경변수가 설정되지 않았습니다: {', '.join(missing)}"
        )

    return {key: os.environ[key] for key in _REQUIRED_ENV_VARS}


def load_config(
    config_dir: Path | None = None,
    env_file: Path | None = None,
) -> Config:
    """설정을 로딩하여 Config 인스턴스를 반환한다.

    Args:
        config_dir: yaml 파일이 위치한 디렉터리 (기본값: <project_root>/config)
        env_file:   .env 파일 경로 (기본값: <project_root>/.env)
    """
    raw = _load_yaml(config_dir or _CONFIG_DIR)
    env_vars = _load_env_vars(env_file)
    return Config(raw, env_vars)
