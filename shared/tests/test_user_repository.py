"""Unit tests for shared.user_repository."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from shared.user_repository import UserRepository, UserRow


def _make_repo(fetchone_value=None):
    conn = MagicMock()
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchone.return_value = fetchone_value
    cur.lastrowid = 99
    conn.cursor.return_value = cur
    return UserRepository(conn), conn, cur


_ROW = {
    "id": 1,
    "email_enc": b"e",
    "email_hmac": b"h",
    "name_enc": b"n",
    "password_hash": "$argon2id$...",
    "is_admin": True,
    "failed_login_count": 0,
    "locked_until": None,
}


def test_find_by_id_returns_userrow():
    repo, _, _ = _make_repo(fetchone_value=_ROW)
    u = repo.find_by_id(1)
    assert isinstance(u, UserRow) and u.id == 1 and u.is_admin is True


def test_find_by_id_returns_none_when_missing():
    repo, _, _ = _make_repo(fetchone_value=None)
    assert repo.find_by_id(99) is None


def test_find_by_email_hmac_uses_hmac_column():
    repo, _, cur = _make_repo(fetchone_value=_ROW)
    repo.find_by_email_hmac(b"x" * 32)
    sql = cur.execute.call_args.args[0]
    assert "email_hmac = %s" in sql


def test_create_returns_lastrowid_and_commits():
    repo, conn, cur = _make_repo()
    uid = repo.create(email_enc=b"e", email_hmac=b"h", name_enc=b"n", password_hash="$x")
    assert uid == 99
    conn.commit.assert_called_once()
    assert cur.execute.call_args.args[0].startswith("INSERT INTO users")


def test_increment_and_reset_failed_login():
    repo, _, cur = _make_repo()
    repo.increment_failed_login(1)
    assert "failed_login_count + 1" in cur.execute.call_args.args[0]
    repo.reset_failed_login(1)
    sql = cur.execute.call_args.args[0]
    assert "failed_login_count = 0" in sql and "locked_until = NULL" in sql


def test_set_lock_writes_locked_until():
    repo, _, cur = _make_repo()
    t = datetime(2026, 4, 17, 21, 0, 0)
    repo.set_lock(1, t)
    assert "locked_until = %s" in cur.execute.call_args.args[0]
    assert cur.execute.call_args.args[1] == (t, 1)


def test_set_admin_updates_admin_flag():
    repo, _, cur = _make_repo()
    repo.set_admin(1, True)
    assert "is_admin = %s" in cur.execute.call_args.args[0]
    assert cur.execute.call_args.args[1] == (True, 1)
