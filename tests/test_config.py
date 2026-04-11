"""config.py 비즈니스 로직 테스트."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from src.config import Config, load_config, _load_env_vars, _load_yaml

# ── 픽스처 ────────────────────────────────────────────────────────────────────

_MINIMAL_RAW: dict = {
    "scheduler": {"poll_interval_seconds": 60, "timezone": "Asia/Seoul"},
    "cafe": {
        "cafe_id": 31672965,
        "cafe_url": "https://cafe.naver.com/test",
        "boards": [
            {"id": 1, "name": "자유게시판", "face_check": False},
            {"id": 2, "name": "사진게시판", "face_check": True, "menu_id": 13, "type": "image"},
        ],
    },
    "face": {"tolerance": 0.55, "reference_dir": "data/faces/"},
    "notification": {"kakao": {"enabled": True, "target_id": "me", "recipients": [
        {"type": "self"},
        {"type": "friend", "friend_uuid": "test-uuid"},
    ]}},
    "summary": {"enabled": True, "model": "claude-3-5-haiku-20241022", "max_tokens": 300},
}

_VALID_ENV: dict[str, str] = {
    "NAVER_ID": "test_id",
    "NAVER_PW": "test_pw",
    "KAKAO_TOKEN": "test_kakao",
    "ANTHROPIC_API_KEY": "test_anthropic",
}


@pytest.fixture()
def cfg() -> Config:
    return Config(_MINIMAL_RAW, _VALID_ENV)


# ── 정상 로딩 테스트 ──────────────────────────────────────────────────────────

class TestConfigLoading:
    def test_poll_interval_parsed(self, cfg: Config) -> None:
        assert cfg.poll_interval == 60

    def test_timezone_parsed(self, cfg: Config) -> None:
        assert cfg.timezone == "Asia/Seoul"

    def test_boards_parsed(self, cfg: Config) -> None:
        assert len(cfg.boards) == 2
        assert cfg.boards[0].name == "자유게시판"
        assert cfg.boards[0].face_check is False
        assert cfg.boards[1].face_check is True

    def test_face_tolerance_parsed(self, cfg: Config) -> None:
        assert cfg.face.tolerance == pytest.approx(0.55)

    def test_cafe_id_parsed(self, cfg: Config) -> None:
        assert cfg.cafe_id == 31672965

    def test_board_menu_id_parsed(self, cfg: Config) -> None:
        assert cfg.boards[1].menu_id == 13
        assert cfg.boards[1].board_type == "image"

    def test_notification_kakao_parsed(self, cfg: Config) -> None:
        assert cfg.notification.kakao.enabled is True
        assert cfg.notification.kakao.target_id == "me"

    def test_recipients_parsed(self, cfg: Config) -> None:
        recipients = cfg.notification.kakao.recipients
        assert len(recipients) == 2
        assert recipients[0].type == "self"
        assert recipients[1].type == "friend"
        assert recipients[1].friend_uuid == "test-uuid"

    def test_summary_parsed(self, cfg: Config) -> None:
        assert cfg.summary.enabled is True
        assert cfg.summary.model == "claude-3-5-haiku-20241022"
        assert cfg.summary.max_tokens == 300

    def test_credentials_loaded_from_env(self, cfg: Config) -> None:
        assert cfg.naver_id == "test_id"
        assert cfg.naver_pw == "test_pw"
        assert cfg.kakao_token == "test_kakao"
        assert cfg.anthropic_api_key == "test_anthropic"


# ── yaml 폴백 테스트 ──────────────────────────────────────────────────────────

class TestYamlFallback:
    def test_loads_config_yaml_when_present(self, tmp_path: Path) -> None:
        (tmp_path / "config.yaml").write_text(
            yaml.dump({"scheduler": {"poll_interval_seconds": 99}}), encoding="utf-8"
        )
        (tmp_path / "config.example.yaml").write_text(
            yaml.dump({"scheduler": {"poll_interval_seconds": 1}}), encoding="utf-8"
        )
        raw = _load_yaml(tmp_path)
        assert raw["scheduler"]["poll_interval_seconds"] == 99

    def test_falls_back_to_example_when_config_yaml_missing(self, tmp_path: Path) -> None:
        (tmp_path / "config.example.yaml").write_text(
            yaml.dump({"scheduler": {"poll_interval_seconds": 42}}), encoding="utf-8"
        )
        raw = _load_yaml(tmp_path)
        assert raw["scheduler"]["poll_interval_seconds"] == 42

    def test_raises_when_no_yaml_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="설정 파일을 찾을 수 없습니다"):
            _load_yaml(tmp_path)


# ── 환경변수 누락 에러 테스트 ─────────────────────────────────────────────────

class TestMissingEnvVars:
    def test_raises_on_missing_all_env_vars(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        for key in ("NAVER_ID", "NAVER_PW", "KAKAO_TOKEN", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("", encoding="utf-8")

        with pytest.raises(EnvironmentError, match="필수 환경변수가 설정되지 않았습니다"):
            _load_env_vars(env_file)

    def test_error_message_lists_missing_keys(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        for key in ("NAVER_ID", "NAVER_PW", "KAKAO_TOKEN"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("NAVER_ID", "set")
        monkeypatch.setenv("NAVER_PW", "set")
        env_file = tmp_path / ".env"
        env_file.write_text("", encoding="utf-8")

        with pytest.raises(EnvironmentError) as exc_info:
            _load_env_vars(env_file)

        msg = str(exc_info.value)
        assert "KAKAO_TOKEN" in msg
        assert "NAVER_ID" not in msg  # 이미 설정된 키는 포함되지 않아야 함

    def test_raises_on_single_missing_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        for key in ("NAVER_ID", "NAVER_PW", "KAKAO_TOKEN"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("NAVER_ID", "id")
        monkeypatch.setenv("NAVER_PW", "pw")
        # KAKAO_TOKEN 누락
        env_file = tmp_path / ".env"
        env_file.write_text("", encoding="utf-8")

        with pytest.raises(EnvironmentError, match="KAKAO_TOKEN"):
            _load_env_vars(env_file)


# ── 폴링 ON/OFF 토글 테스트 ───────────────────────────────────────────────────

class TestPollingToggle:
    def test_polling_enabled_by_default(self, cfg: Config) -> None:
        assert cfg.polling_enabled is True

    def test_disable_polling(self, cfg: Config) -> None:
        cfg.disable_polling()
        assert cfg.polling_enabled is False

    def test_enable_polling(self, cfg: Config) -> None:
        cfg.disable_polling()
        cfg.enable_polling()
        assert cfg.polling_enabled is True

    def test_toggle_returns_new_state(self, cfg: Config) -> None:
        result = cfg.toggle_polling()
        assert result is False
        assert cfg.polling_enabled is False

    def test_toggle_twice_restores_original(self, cfg: Config) -> None:
        cfg.toggle_polling()
        cfg.toggle_polling()
        assert cfg.polling_enabled is True

    def test_disable_is_idempotent(self, cfg: Config) -> None:
        cfg.disable_polling()
        cfg.disable_polling()
        assert cfg.polling_enabled is False


# ── load_config 통합 테스트 ───────────────────────────────────────────────────

class TestLoadConfig:
    def test_load_config_end_to_end(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """config.yaml + .env 파일로 전체 load_config 흐름을 검증한다."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            yaml.dump({
                "scheduler": {"poll_interval_seconds": 120, "timezone": "Asia/Seoul"},
                "cafe": {"url": "https://cafe.naver.com/test", "boards": []},
                "face": {"tolerance": 0.6, "reference_dir": "data/faces/"},
                "notification": {"kakao": {"enabled": False, "target_id": "me"}},
                "summary": {"enabled": False, "model": "claude-3-haiku", "max_tokens": 100},
            }),
            encoding="utf-8",
        )
        env_file = tmp_path / ".env"
        env_file.write_text(
            "NAVER_ID=myid\nNAVER_PW=mypw\nKAKAO_TOKEN=mytoken\nANTHROPIC_API_KEY=mykey\n",
            encoding="utf-8",
        )

        # 기존 환경변수 오염 방지
        for key in ("NAVER_ID", "NAVER_PW", "KAKAO_TOKEN", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(key, raising=False)

        cfg = load_config(config_dir=config_dir, env_file=env_file)

        assert cfg.poll_interval == 120
        assert cfg.naver_id == "myid"
        assert cfg.kakao_token == "mytoken"
        assert cfg.notification.kakao.enabled is False
