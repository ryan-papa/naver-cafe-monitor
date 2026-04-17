"""Static structural checks for the auth schema DDL (TA-02)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

DDL_PATH = Path(__file__).resolve().parents[1] / "migrations" / "20260417_auth_schema.sql"


@pytest.fixture(scope="module")
def ddl() -> str:
    assert DDL_PATH.exists(), f"{DDL_PATH} missing"
    return DDL_PATH.read_text()


@pytest.mark.parametrize(
    "table",
    ["users", "refresh_tokens", "auth_events", "rate_limit_buckets"],
)
def test_required_tables_declared(ddl: str, table: str):
    pattern = re.compile(rf"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+{table}\b", re.IGNORECASE)
    assert pattern.search(ddl), f"{table} table missing"


def test_users_has_email_hmac_unique(ddl: str):
    assert re.search(r"UNIQUE\s+KEY\s+uk_email_hmac", ddl)


def test_users_has_is_admin_column(ddl: str):
    assert re.search(r"is_admin\s+BOOLEAN", ddl, re.IGNORECASE)


def test_refresh_tokens_single_session_by_user_pk(ddl: str):
    # user_id를 PK로 선언 → 단일 세션
    assert re.search(r"user_id\s+BIGINT\s+NOT\s+NULL\s+PRIMARY\s+KEY", ddl, re.IGNORECASE)


def test_refresh_tokens_cascade_on_user_delete(ddl: str):
    assert "ON DELETE CASCADE" in ddl


def test_auth_events_enum_contains_reuse_detection(ddl: str):
    assert "refresh_reuse_detected" in ddl


def test_rate_limit_bucket_has_window_end_index(ddl: str):
    assert re.search(r"INDEX\s+idx_window_end", ddl)


def test_charset_utf8mb4(ddl: str):
    assert ddl.count("utf8mb4") >= 4, "모든 테이블이 utf8mb4 기반이어야 함"
