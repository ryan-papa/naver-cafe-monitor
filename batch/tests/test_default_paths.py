from pathlib import Path

from src.config import _CONFIG_DIR, _REPO_ROOT as _CFG_REPO_ROOT
from src.crawler.session import _DEFAULT_COOKIE_PATH
from src.messaging.kakao_auth import _DEFAULT_TOKEN_PATH as _KAKAO_TOKEN_PATH
from src.storage.google_photos import _DEFAULT_TOKEN_PATH as _GPHOTOS_TOKEN_PATH

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_config_dir_is_repo_root_config():
    assert _CONFIG_DIR == _REPO_ROOT / "config"
    assert _CFG_REPO_ROOT == _REPO_ROOT


def test_kakao_token_path_is_repo_root_config():
    assert _KAKAO_TOKEN_PATH == _REPO_ROOT / "config" / "kakao_token.json"


def test_gphotos_token_path_is_repo_root_config():
    assert _GPHOTOS_TOKEN_PATH == _REPO_ROOT / "config" / "google_token.json"


def test_cookie_path_is_repo_root_data():
    assert _DEFAULT_COOKIE_PATH == _REPO_ROOT / "data" / "cookies.json"
