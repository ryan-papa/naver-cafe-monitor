"""Host 기반 internal/external 분류 (TA-26).

PRD v2 F-17: suffix 매칭.
- `*.eepp.shop` → internal (mTLS, 2FA 면제)
- `*.eepp.store` → external (2FA 필수)
- 그 외 → external (안전 측)

환경변수 override:
- `AUTH_INTERNAL_HOST_SUFFIXES`: 콤마 구분 (예: ".eepp.shop,.localhost")
- `AUTH_EXTERNAL_HOST_SUFFIXES`: 콤마 구분 (예: ".eepp.store")
둘 다 매치 안 하면 external 로 fallback.
"""
from __future__ import annotations

import os
from typing import Literal

HostContext = Literal["internal", "external"]

_DEFAULT_INTERNAL = (".eepp.shop",)
_DEFAULT_EXTERNAL = (".eepp.store",)


def _parse_suffixes(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return default
    return tuple(s.strip().lower() for s in value.split(",") if s.strip())


def classify(hostname: str | None) -> HostContext:
    if not hostname:
        return "external"
    host = hostname.strip().lower()
    # IPv6 bracketed host 등 비정상 입력 방어
    if not host:
        return "external"

    internals = _parse_suffixes(
        os.environ.get("AUTH_INTERNAL_HOST_SUFFIXES"), _DEFAULT_INTERNAL
    )
    externals = _parse_suffixes(
        os.environ.get("AUTH_EXTERNAL_HOST_SUFFIXES"), _DEFAULT_EXTERNAL
    )

    for suf in internals:
        if host == suf.lstrip(".") or host.endswith(suf):
            return "internal"
    for suf in externals:
        if host == suf.lstrip(".") or host.endswith(suf):
            return "external"
    return "external"


def is_internal(hostname: str | None) -> bool:
    return classify(hostname) == "internal"
