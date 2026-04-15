#!/usr/bin/env python3
"""카카오 OAuth 토큰 초기 셋업 스크립트.

로컬 HTTP 서버를 기동하여 인가 코드를 수신하고,
access_token + refresh_token을 발급받아 config/kakao_token.json에 저장한다.

사용법:
    python scripts/kakao_setup.py

필요 환경변수 (.env):
    KAKAO_CLIENT_ID — 카카오 REST API 키
    KAKAO_CLIENT_SECRET — 카카오 클라이언트 시크릿
"""
from __future__ import annotations

import json
import os
import sys
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from dotenv import load_dotenv

_BATCH_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BATCH_ROOT.parent
_TOKEN_PATH = _BATCH_ROOT / "config" / "kakao_token.json"
_PORT = 9999
_REDIRECT_URI = f"http://localhost:{_PORT}/callback"
_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"


class _CallbackHandler(BaseHTTPRequestHandler):
    """인가 코드 콜백을 처리하는 핸들러."""

    auth_code: str | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)
        code = params.get("code", [None])[0]

        if code:
            _CallbackHandler.auth_code = code
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>OK</h2>"
                b"<p>This window can be closed.</p></body></html>"
            )
        else:
            error = params.get("error_description", ["unknown"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<html><body><h2>Error: {error}</h2></body></html>".encode())

    def log_message(self, format, *args) -> None:
        pass  # suppress access log


def _exchange_token(client_id: str, client_secret: str, code: str) -> dict:
    """인가 코드를 토큰으로 교환한다."""
    resp = requests.post(
        _TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": _REDIRECT_URI,
            "code": code,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"[ERROR] 토큰 교환 실패: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def main() -> None:
    load_dotenv(_REPO_ROOT / ".env")

    client_id = os.getenv("KAKAO_CLIENT_ID")
    client_secret = os.getenv("KAKAO_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("[ERROR] .env에 KAKAO_CLIENT_ID와 KAKAO_CLIENT_SECRET을 설정하세요.", file=sys.stderr)
        sys.exit(1)

    # 로컬 서버 시작
    try:
        server = HTTPServer(("localhost", _PORT), _CallbackHandler)
    except OSError as e:
        print(f"[ERROR] 포트 {_PORT} 사용 불가: {e}", file=sys.stderr)
        sys.exit(1)

    # 브라우저 열기
    auth_url = (
        f"{_AUTH_URL}?client_id={client_id}"
        f"&redirect_uri={_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=talk_message"
    )
    print(f"브라우저에서 카카오 로그인을 진행하세요...")
    webbrowser.open(auth_url)

    # 콜백 대기
    print(f"인가 코드 대기 중 (http://localhost:{_PORT}/callback)...")
    while _CallbackHandler.auth_code is None:
        server.handle_request()

    server.server_close()
    code = _CallbackHandler.auth_code
    print(f"인가 코드 수신 완료")

    # 토큰 교환
    result = _exchange_token(client_id, client_secret, code)

    # 토큰 파일 저장
    now = int(time.time())
    token_data = {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "expires_at": now + result.get("expires_in", 21599),
        "refresh_token_expires_at": now + result.get("refresh_token_expires_in", 5183999),
    }

    _TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_PATH.write_text(
        json.dumps(token_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"토큰 저장 완료: {_TOKEN_PATH}")
    print(f"  access_token 유효기간: {result.get('expires_in', 0) // 3600}시간")
    print(f"  refresh_token 유효기간: {result.get('refresh_token_expires_in', 0) // 86400}일")


if __name__ == "__main__":
    main()
