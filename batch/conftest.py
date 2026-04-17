"""Batch 테스트용 sys.path 프록시.

기존 batch 테스트는 `from src.xxx` 스타일 import 를 가정한다.
monorepo 루트에서 `--import-mode=importlib` 로 실행할 때도 동일하게 동작하도록
batch 디렉터리를 sys.path 앞에 추가한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

_BATCH_ROOT = Path(__file__).resolve().parent
if str(_BATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_BATCH_ROOT))
