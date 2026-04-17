"""Auth 공통 암호화 유틸 (TA-03).

포함:
- AES-256-GCM 대칭 암호화 (이메일/이름/TOTP secret)
- HMAC-SHA256 룩업 인덱스 (이메일 중복 조회용)
- argon2id 비밀번호 해시·검증
- RSA-OAEP-SHA256 공개키 암호화·복호화 (E2E 민감 필드)
"""
from __future__ import annotations

import hashlib
import hmac as _hmac
import os

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_AES_IV_LEN = 12  # GCM 권장
_ARGON2 = PasswordHasher(memory_cost=64 * 1024, time_cost=3, parallelism=1)


# ─────────────── AES-GCM ───────────────
def aes_gcm_encrypt(plaintext: bytes, key: bytes) -> bytes:
    """키(32B) + 평문 → iv(12B) || ciphertext+tag(16B)."""
    if len(key) != 32:
        raise ValueError("AES key must be 32 bytes (AES-256)")
    iv = os.urandom(_AES_IV_LEN)
    ct = AESGCM(key).encrypt(iv, plaintext, None)
    return iv + ct


def aes_gcm_decrypt(blob: bytes, key: bytes) -> bytes:
    if len(key) != 32:
        raise ValueError("AES key must be 32 bytes (AES-256)")
    if len(blob) < _AES_IV_LEN + 16:
        raise ValueError("ciphertext too short")
    iv, ct = blob[:_AES_IV_LEN], blob[_AES_IV_LEN:]
    return AESGCM(key).decrypt(iv, ct, None)


# ─────────────── HMAC ───────────────
def hmac_sha256(msg: bytes, key: bytes) -> bytes:
    """이메일 룩업 인덱스(고정 길이 32B)."""
    return _hmac.new(key, msg, hashlib.sha256).digest()


# ─────────────── argon2id ───────────────
def argon2_hash(password: str) -> str:
    return _ARGON2.hash(password)


def argon2_verify(password: str, hashed: str) -> bool:
    try:
        return _ARGON2.verify(hashed, password)
    except (VerifyMismatchError, InvalidHash):
        return False


def argon2_needs_rehash(hashed: str) -> bool:
    try:
        return _ARGON2.check_needs_rehash(hashed)
    except InvalidHash:
        return True


# ─────────────── RSA-OAEP ───────────────
_OAEP = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)


def _load_private(pem: bytes | str) -> rsa.RSAPrivateKey:
    if isinstance(pem, str):
        pem = pem.encode()
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("not an RSA private key")
    return key


def _load_public(pem: bytes | str) -> rsa.RSAPublicKey:
    if isinstance(pem, str):
        pem = pem.encode()
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, rsa.RSAPublicKey):
        raise ValueError("not an RSA public key")
    return key


def rsa_oaep_encrypt(public_pem: bytes | str, plaintext: bytes) -> bytes:
    return _load_public(public_pem).encrypt(plaintext, _OAEP)


def rsa_oaep_decrypt(private_pem: bytes | str, ciphertext: bytes) -> bytes:
    return _load_private(private_pem).decrypt(ciphertext, _OAEP)
