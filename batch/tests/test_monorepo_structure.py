"""모노레포 구조 검증 테스트."""
from pathlib import Path

_BATCH_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BATCH_ROOT.parent


def test_batch_directory_exists():
    assert (_REPO_ROOT / "batch").is_dir()


def test_batch_src_exists():
    assert (_BATCH_ROOT / "src").is_dir()
    assert (_BATCH_ROOT / "src" / "__init__.py").is_file()


def test_batch_tests_exists():
    assert (_BATCH_ROOT / "tests").is_dir()


def test_batch_config_exists():
    assert (_BATCH_ROOT / "config").is_dir()
    assert (_BATCH_ROOT / "config" / "config.example.yaml").is_file()


def test_top_level_directories_exist():
    for name in ("api", "web", "db", "shared"):
        assert (_REPO_ROOT / name).is_dir(), f"{name}/ 디렉토리 없음"


def test_shared_module():
    assert (_REPO_ROOT / "shared" / "__init__.py").is_file()
    assert (_REPO_ROOT / "shared" / "database.py").is_file()


def test_env_at_repo_root():
    assert (_REPO_ROOT / ".env.example").is_file()


def test_config_paths_resolve():
    """config.py의 _BATCH_ROOT가 batch/ 를 가리키는지 검증."""
    from src.config import _BATCH_ROOT as cfg_batch_root, _REPO_ROOT as cfg_repo_root

    assert cfg_batch_root == _BATCH_ROOT
    assert cfg_repo_root == _REPO_ROOT
