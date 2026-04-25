"""Google OAuth login routes for the admin UI."""
from __future__ import annotations

import base64
import json
import os
import secrets
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, RedirectResponse

from api.src.auth.cookies import set_access_cookie, set_csrf_cookie, set_refresh_cookie
from api.src.auth.dependencies import get_user_repository
from api.src.auth.token_service import issue_pair
from shared.auth_events import log_auth_event
from shared.crypto import aes_gcm_encrypt, argon2_hash, hmac_sha256
from shared.refresh_token_repository import RefreshTokenRepository
from shared.user_repository import UserRepository

router = APIRouter(tags=["google-oauth"])

STATE_COOKIE = "google_oauth_state"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
LOGIN_SUCCESS_PATH = "/admin/posts"


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{name} not configured",
        )
    return value


def _allowed_emails() -> set[str]:
    raw = (
        os.environ.get("GOOGLE_ADMIN_ALLOWED_EMAILS")
        or os.environ.get("AUTH_ADMIN_ALLOWED_EMAILS")
        or ""
    )
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def _is_allowed(email: str) -> bool:
    allowed = _allowed_emails()
    return bool(allowed) and email.lower() in allowed


def _aes_key() -> bytes:
    return base64.b64decode(_required_env("AUTH_AES_KEY"))


def _hmac_key() -> bytes:
    return base64.b64decode(_required_env("AUTH_HMAC_KEY"))


def _redirect_uri(request: Request) -> str:
    configured = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    if configured:
        return configured
    return str(request.url_for("google_oauth_callback"))


def _post_form(url: str, data: dict[str, str]) -> dict:
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={"content-type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read().decode())


def _get_json(url: str, access_token: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read().decode())


def _find_or_create_admin_user(
    *,
    email: str,
    name: str,
    user_repo: UserRepository,
) -> int:
    email_hmac = hmac_sha256(email.lower().encode(), _hmac_key())
    existing = user_repo.find_by_email_hmac(email_hmac)
    if existing is not None:
        if existing.is_admin:
            return existing.id
        if _is_allowed(email):
            user_repo.set_admin(existing.id, True)
            return existing.id
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin permission required",
            )

    if not _is_allowed(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google account is not allowed",
        )

    aes = _aes_key()
    return user_repo.create(
        email_enc=aes_gcm_encrypt(email.encode(), aes),
        email_hmac=email_hmac,
        name_enc=aes_gcm_encrypt((name or email).encode(), aes),
        password_hash=argon2_hash(secrets.token_urlsafe(32)),
        is_admin=True,
    )


@router.get("/oauth2/authorization/google")
def google_oauth_start(request: Request) -> RedirectResponse:
    client_id = _required_env("GOOGLE_CLIENT_ID")
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    response = RedirectResponse(
        f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}", status_code=302
    )
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )
    return response


@router.get("/login/oauth2/code/google", name="google_oauth_callback")
def google_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    user_repo: UserRepository = Depends(get_user_repository),
):
    if error:
        return PlainTextResponse("oauth_login_failed", status_code=401)
    expected_state = request.cookies.get(STATE_COOKIE)
    if not expected_state or not state or not secrets.compare_digest(expected_state, state):
        return PlainTextResponse("oauth_state_invalid", status_code=400)
    if not code:
        return PlainTextResponse("oauth_code_missing", status_code=400)

    token = _post_form(
        GOOGLE_TOKEN_URL,
        {
            "code": code,
            "client_id": _required_env("GOOGLE_CLIENT_ID"),
            "client_secret": _required_env("GOOGLE_CLIENT_SECRET"),
            "redirect_uri": _redirect_uri(request),
            "grant_type": "authorization_code",
        },
    )
    userinfo = _get_json(GOOGLE_USERINFO_URL, token["access_token"])
    email = str(userinfo.get("email") or "").strip().lower()
    email_verified = userinfo.get("email_verified")
    if not email or email_verified is not True:
        return PlainTextResponse("oauth_email_unverified", status_code=403)

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        user_id = _find_or_create_admin_user(
            email=email,
            name=str(userinfo.get("name") or email),
            user_repo=user_repo,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            return PlainTextResponse("oauth_login_forbidden", status_code=403)
        raise

    refresh_repo = RefreshTokenRepository(user_repo.conn)
    pair = issue_pair(user_id, repo=refresh_repo)
    log_auth_event("login_ok", user_id=user_id, ip=ip, user_agent=ua)

    response = RedirectResponse(LOGIN_SUCCESS_PATH, status_code=302)
    response.delete_cookie(STATE_COOKIE, path="/")
    set_access_cookie(response, pair.access_token)
    set_refresh_cookie(response, pair.refresh_token)
    set_csrf_cookie(response, pair.csrf_token)
    return response
