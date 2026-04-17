"""Unit tests for shared.auth_events (TA-07)."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from shared import auth_events


class _FakeCursor:
    def __init__(self):
        self.executed: list[tuple[str, tuple]] = []

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConnection:
    def __init__(self):
        self.cursor_obj = _FakeCursor()
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1


@pytest.fixture
def fake_conn():
    conn = _FakeConnection()

    @contextmanager
    def _cm():
        yield conn

    def _factory():
        return _cm()

    return conn, _factory


def test_log_auth_event_inserts_and_commits(fake_conn):
    conn, factory = fake_conn
    auth_events.log_auth_event(
        "login_ok",
        user_id=7,
        ip="1.2.3.4",
        user_agent="Mozilla/5.0",
        connection_factory=factory,
    )
    assert conn.commits == 1
    assert len(conn.cursor_obj.executed) == 1
    sql, params = conn.cursor_obj.executed[0]
    assert "INSERT INTO auth_events" in sql
    assert params == (7, "login_ok", "1.2.3.4", "Mozilla/5.0")


def test_log_auth_event_truncates_user_agent(fake_conn):
    conn, factory = fake_conn
    long_ua = "x" * 400
    auth_events.log_auth_event(
        "signup",
        user_id=1,
        ip="::1",
        user_agent=long_ua,
        connection_factory=factory,
    )
    _, params = conn.cursor_obj.executed[0]
    assert len(params[3]) == 255


def test_log_auth_event_allows_null_user(fake_conn):
    conn, factory = fake_conn
    auth_events.log_auth_event(
        "login_fail",
        ip="1.2.3.4",
        connection_factory=factory,
    )
    _, params = conn.cursor_obj.executed[0]
    assert params == (None, "login_fail", "1.2.3.4", None)


def test_event_type_literals_cover_all_db_enum_values():
    # PRD/스키마와 싱크 유지
    import re
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parents[2] / "db" / "migrations" / "20260417_auth_schema.sql"
    ).read_text()
    m = re.search(r"event_type\s+ENUM\(([^)]+)\)", sql)
    assert m, "event_type ENUM declaration not found"
    db_values = {v.strip().strip("'") for v in m.group(1).split(",")}

    from typing import get_args

    py_values = set(get_args(auth_events.AuthEventType))
    assert db_values == py_values, f"mismatch db={db_values} py={py_values}"
