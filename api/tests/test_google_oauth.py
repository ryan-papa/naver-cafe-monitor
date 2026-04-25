from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from api.src.auth.dependencies import get_user_repository
from api.src.auth.google_oauth import STATE_COOKIE, _find_or_create_admin_user
from api.src.main import app
from shared.crypto import hmac_sha256
from shared.user_repository import UserRow


AES_KEY = b"a" * 32
HMAC_KEY = b"h" * 32


def _env(monkeypatch):
    monkeypatch.setenv("AUTH_AES_KEY", base64.b64encode(AES_KEY).decode())
    monkeypatch.setenv("AUTH_HMAC_KEY", base64.b64encode(HMAC_KEY).decode())
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-32-bytes-xxxxxxxxxxx")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
    monkeypatch.setenv("GOOGLE_ADMIN_ALLOWED_EMAILS", "admin@example.com")


def test_google_start_redirects_to_google_and_sets_state(monkeypatch):
    _env(monkeypatch)
    r = TestClient(app).get("/oauth2/authorization/google", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert STATE_COOKIE in r.cookies


def test_existing_allowed_non_admin_user_is_promoted(monkeypatch):
    _env(monkeypatch)
    repo = MagicMock()
    user = UserRow(
        id=7,
        email_enc=b"e",
        email_hmac=hmac_sha256(b"admin@example.com", HMAC_KEY),
        name_enc=b"n",
        password_hash="$argon2id$...",
        is_admin=False,
        failed_login_count=0,
        locked_until=None,
    )
    repo.find_by_email_hmac.return_value = user

    user_id = _find_or_create_admin_user(
        email="admin@example.com",
        name="Admin",
        user_repo=repo,
    )

    assert user_id == 7
    repo.set_admin.assert_called_once_with(7, True)


def test_existing_non_allowed_non_admin_user_is_forbidden(monkeypatch):
    _env(monkeypatch)
    repo = MagicMock()
    user = UserRow(
        id=8,
        email_enc=b"e",
        email_hmac=hmac_sha256(b"other@example.com", HMAC_KEY),
        name_enc=b"n",
        password_hash="$argon2id$...",
        is_admin=False,
        failed_login_count=0,
        locked_until=None,
    )
    repo.find_by_email_hmac.return_value = user

    try:
        _find_or_create_admin_user(
            email="other@example.com",
            name="Other",
            user_repo=repo,
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("expected 403")


def test_google_callback_rejects_invalid_state(monkeypatch):
    _env(monkeypatch)
    app.dependency_overrides[get_user_repository] = lambda: MagicMock()
    try:
        r = TestClient(app).get(
            "/login/oauth2/code/google?code=x&state=bad",
            cookies={STATE_COOKIE: "good"},
        )
        assert r.status_code == 400
        assert r.text == "oauth_state_invalid"
    finally:
        app.dependency_overrides.clear()
        os.environ.pop("GOOGLE_ADMIN_ALLOWED_EMAILS", None)
