"""Unit tests for scripts.auth.generate_secrets (TA-01)."""
from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization

from scripts.auth import generate_secrets as gs


def test_rsa_keypair_is_valid_pem_pair():
    priv_pem, pub_pem = gs.generate_rsa_keypair()

    priv_key = serialization.load_pem_private_key(priv_pem.encode(), password=None)
    pub_key = serialization.load_pem_public_key(pub_pem.encode())

    assert priv_key.key_size == 2048
    assert priv_key.public_key().public_numbers() == pub_key.public_numbers()


@pytest.mark.parametrize("n", [16, 24, 32])
def test_generate_b64_key_length(n):
    key = gs.generate_b64_key(n)
    raw = base64.b64decode(key)
    assert len(raw) == n


def test_generate_b64_key_is_random():
    a = gs.generate_b64_key(32)
    b = gs.generate_b64_key(32)
    assert a != b


def test_parse_and_render_dotenv_roundtrip():
    text = "A=1\nB=hello world\n# comment\n\nC=x=y=z\n"
    env = gs.parse_dotenv(text)
    assert env == {"A": "1", "B": "hello world", "C": "x=y=z"}

    rendered = gs.render_dotenv(env)
    env2 = gs.parse_dotenv(rendered)
    assert env == env2


def test_escape_pem_converts_newlines():
    pem = "-----BEGIN PUBLIC KEY-----\nabc\nxyz\n-----END PUBLIC KEY-----\n"
    escaped = gs.escape_pem(pem)
    assert "\n" not in escaped
    assert "\\n" in escaped


def test_build_auth_secrets_has_all_keys():
    out = gs.build_auth_secrets()
    assert set(out.keys()) == set(gs.AUTH_KEYS)

    # RSA PEM starts with header (after escaping, backslash-n replaces newlines)
    assert out["AUTH_RSA_PRIVATE_KEY"].startswith("-----BEGIN PRIVATE KEY-----")
    assert out["AUTH_RSA_PUBLIC_KEY"].startswith("-----BEGIN PUBLIC KEY-----")

    for sym in ("AUTH_AES_KEY", "AUTH_HMAC_KEY", "AUTH_JWT_SECRET"):
        raw = base64.b64decode(out[sym])
        assert len(raw) == 32
