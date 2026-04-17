"""CI 에서 shared 모듈 import 경로 보장.

로컬은 루트 pyproject.toml + --import-mode=importlib 로 처리되지만,
CI 의 api job 은 cwd=api 에서 api/pyproject.toml 만 참조하므로 shared 경로 누락됨.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
