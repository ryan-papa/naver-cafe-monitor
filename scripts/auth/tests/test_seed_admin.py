"""Unit tests for scripts.auth.seed_admin (TA-14)."""
from __future__ import annotations

import os
from contextlib import contextmanager

import pytest

from scripts.auth import seed_admin as sa
from shared.crypto import aes_gcm_decrypt, argon2_verify, hmac_sha256


AES_KEY = os.urandom(32)
HMAC_KEY = os.urandom(32)


class _FakeCursor:
    def __init__(self, existing: dict | None = None):
        self._existing = existing
        self.executed: list[tuple[str, tuple]] = []
        self._last = None
        self.lastrowid = 42

    def execute(self, sql, params=()):
        self.executed.append((sql.strip(), params))
        if sql.strip().startswith("SELECT id FROM users"):
            self._last = self._existing
        else:
            self._last = None

    def fetchone(self):
        return self._last

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, existing=None):
        self.cursor_obj = _FakeCursor(existing)
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1


def _factory_for(conn: _FakeConn):
    @contextmanager
    def _cm():
        yield conn

    return lambda: _cm()


def test_creates_new_admin_when_not_exists():
    conn = _FakeConn(existing=None)
    action, uid = sa.seed_admin(
        "admin@example.com",
        "Admin",
        "strongPW!123",
        aes_key=AES_KEY,
        hmac_key=HMAC_KEY,
        connection_factory=_factory_for(conn),
    )
    assert action == "created"
    assert uid == 42
    assert conn.commits == 1

    inserts = [e for e in conn.cursor_obj.executed if e[0].startswith("INSERT INTO users")]
    assert len(inserts) == 1
    sql, params = inserts[0]
    email_enc, email_hmac, name_enc, pw_hash = params

    # email_hmac 결정적
    assert email_hmac == hmac_sha256(b"admin@example.com", HMAC_KEY)

    # email/name 복호화 가능
    assert aes_gcm_decrypt(email_enc, AES_KEY) == b"admin@example.com"
    assert aes_gcm_decrypt(name_enc, AES_KEY) == b"Admin"

    # pw_hash argon2 검증
    assert argon2_verify("strongPW!123", pw_hash)
    assert not argon2_verify("wrong", pw_hash)


def test_skip_when_exists_without_force():
    conn = _FakeConn(existing={"id": 7})
    action, uid = sa.seed_admin(
        "admin@example.com",
        "Admin",
        "pw",
        aes_key=AES_KEY,
        hmac_key=HMAC_KEY,
        connection_factory=_factory_for(conn),
    )
    assert action == "skipped"
    assert uid == 7
    # INSERT/UPDATE 없어야 함
    assert not any(
        e[0].startswith(("INSERT INTO users", "UPDATE users"))
        for e in conn.cursor_obj.executed
    )


def test_force_updates_password_and_name():
    conn = _FakeConn(existing={"id": 9})
    action, uid = sa.seed_admin(
        "admin@example.com",
        "NewAdmin",
        "newPW",
        force=True,
        aes_key=AES_KEY,
        hmac_key=HMAC_KEY,
        connection_factory=_factory_for(conn),
    )
    assert action == "updated"
    assert uid == 9
    updates = [e for e in conn.cursor_obj.executed if e[0].startswith("UPDATE users")]
    assert len(updates) == 1


def test_email_normalized_to_lowercase_for_hmac():
    conn = _FakeConn(existing=None)
    sa.seed_admin(
        "Admin@Example.COM",
        "Admin",
        "pw",
        aes_key=AES_KEY,
        hmac_key=HMAC_KEY,
        connection_factory=_factory_for(conn),
    )
    _, params = next(
        e for e in conn.cursor_obj.executed if e[0].startswith("INSERT INTO users")
    )
    assert params[1] == hmac_sha256(b"admin@example.com", HMAC_KEY)


def test_main_fails_without_env(monkeypatch, capsys):
    monkeypatch.delenv("INITIAL_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    rc = sa.main([])
    assert rc == 1
    err = capsys.readouterr().err
    assert "INITIAL_ADMIN" in err
