"""Unit tests for shared.host_classifier (TA-26)."""
from __future__ import annotations

import pytest

from shared import host_classifier as hc


@pytest.mark.parametrize(
    "hostname",
    ["ncm.eepp.shop", "api.eepp.shop", "eepp.shop", "a.b.eepp.shop"],
)
def test_internal_suffix(hostname):
    assert hc.classify(hostname) == "internal"
    assert hc.is_internal(hostname)


@pytest.mark.parametrize(
    "hostname", ["ncm.eepp.store", "eepp.store", "something.example.com"]
)
def test_external_suffix_or_unknown(hostname):
    assert hc.classify(hostname) == "external"
    assert not hc.is_internal(hostname)


def test_empty_or_none_defaults_to_external():
    assert hc.classify(None) == "external"
    assert hc.classify("") == "external"
    assert hc.classify("   ") == "external"


def test_case_insensitive():
    assert hc.classify("NCM.EEPP.SHOP") == "internal"


def test_env_override_internal(monkeypatch):
    monkeypatch.setenv("AUTH_INTERNAL_HOST_SUFFIXES", ".internal.local,.corp.example")
    monkeypatch.setenv("AUTH_EXTERNAL_HOST_SUFFIXES", ".public.example")
    assert hc.classify("foo.internal.local") == "internal"
    assert hc.classify("bar.corp.example") == "internal"
    assert hc.classify("x.public.example") == "external"
    # 기본 eepp.shop 이 override 에 없으므로 unknown → external
    assert hc.classify("ncm.eepp.shop") == "external"


def test_apex_domain_match():
    # 호스트가 정확히 suffix 한 자릿수라도 매칭
    assert hc.classify("eepp.shop") == "internal"
    assert hc.classify("eepp.store") == "external"
