"""Unit tests for shared.crypto (TA-03)."""
from __future__ import annotations

import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from shared import crypto


@pytest.fixture(scope="module")
def aes_key() -> bytes:
    return os.urandom(32)


@pytest.fixture(scope="module")
def rsa_pems() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return priv, pub


# ── AES-GCM ──
def test_aes_gcm_roundtrip(aes_key):
    pt = "hosekim92@naver.com".encode()
    ct = crypto.aes_gcm_encrypt(pt, aes_key)
    assert ct[:12] != pt  # IV 포함
    assert crypto.aes_gcm_decrypt(ct, aes_key) == pt


def test_aes_gcm_produces_distinct_ciphertexts(aes_key):
    pt = b"same plaintext"
    a = crypto.aes_gcm_encrypt(pt, aes_key)
    b = crypto.aes_gcm_encrypt(pt, aes_key)
    assert a != b  # IV 랜덤 → 매번 달라야 함


def test_aes_gcm_rejects_wrong_key_length():
    with pytest.raises(ValueError):
        crypto.aes_gcm_encrypt(b"x", b"short")
    with pytest.raises(ValueError):
        crypto.aes_gcm_decrypt(b"x" * 30, b"short")


def test_aes_gcm_tamper_detection(aes_key):
    ct = bytearray(crypto.aes_gcm_encrypt(b"hello", aes_key))
    ct[-1] ^= 0x01  # tag 조작
    with pytest.raises(Exception):
        crypto.aes_gcm_decrypt(bytes(ct), aes_key)


# ── HMAC ──
def test_hmac_sha256_deterministic():
    key = b"k" * 32
    assert crypto.hmac_sha256(b"email", key) == crypto.hmac_sha256(b"email", key)


def test_hmac_sha256_distinct_for_different_keys():
    a = crypto.hmac_sha256(b"email", b"k1" * 16)
    b = crypto.hmac_sha256(b"email", b"k2" * 16)
    assert a != b


def test_hmac_sha256_length():
    assert len(crypto.hmac_sha256(b"x", b"k" * 32)) == 32


# ── argon2id ──
def test_argon2_hash_verify_ok():
    h = crypto.argon2_hash("chateauUS032233!@#$%")
    assert h.startswith("$argon2id$")
    assert crypto.argon2_verify("chateauUS032233!@#$%", h)


def test_argon2_verify_mismatch():
    h = crypto.argon2_hash("correct")
    assert not crypto.argon2_verify("wrong", h)


def test_argon2_verify_invalid_hash():
    assert not crypto.argon2_verify("x", "not-a-hash")


def test_argon2_hashes_are_distinct_for_same_password():
    a = crypto.argon2_hash("same")
    b = crypto.argon2_hash("same")
    assert a != b  # salt 랜덤


# ── RSA-OAEP ──
def test_rsa_oaep_roundtrip(rsa_pems):
    priv, pub = rsa_pems
    pt = b"secret password"
    ct = crypto.rsa_oaep_encrypt(pub, pt)
    assert crypto.rsa_oaep_decrypt(priv, ct) == pt


def test_rsa_oaep_ciphertext_differs_per_encryption(rsa_pems):
    _, pub = rsa_pems
    a = crypto.rsa_oaep_encrypt(pub, b"same")
    b = crypto.rsa_oaep_encrypt(pub, b"same")
    assert a != b  # OAEP 내부 랜덤


def test_rsa_load_rejects_non_rsa_pem():
    from cryptography.hazmat.primitives.asymmetric import ed25519

    ed = ed25519.Ed25519PrivateKey.generate()
    pem = ed.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    with pytest.raises(ValueError):
        crypto.rsa_oaep_decrypt(pem, b"x")
