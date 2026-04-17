#!/usr/bin/env python3
"""초기 관리자 시드 스크립트 (TA-14).

환경변수로 관리자 계정을 users 테이블에 생성한다.

필수 환경변수 (sops .env.enc 또는 shell env):
- INITIAL_ADMIN_EMAIL
- INITIAL_ADMIN_PASSWORD
- INITIAL_ADMIN_NAME (기본: "Admin")
- AUTH_AES_KEY, AUTH_HMAC_KEY (TA-01 에서 주입)

동작:
- 이미 동일 이메일이 있으면 skip (종료코드 0)
- --force: 기존 계정의 password/name 덮어쓰기 (is_admin=TRUE)
- TOTP 는 최초 로그인 흐름에서 등록 → 여기서는 totp_enabled=FALSE 로 두고 필수 플래그만 기록

실행 예시 (외부에서 sops 로 env 주입):
    sops exec-env --input-type dotenv .env.enc 'python scripts/auth/seed_admin.py'
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path
from typing import Protocol

# 루트 import 보장
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from shared.crypto import aes_gcm_encrypt, argon2_hash, hmac_sha256  # noqa: E402


class _ConnectionFactory(Protocol):
    def __call__(self):
        """Returns object usable as `with ... as conn`."""


def _default_cm():
    from shared.database import connect

    return connect()


def _load_keys() -> tuple[bytes, bytes]:
    aes = os.environ.get("AUTH_AES_KEY")
    hmac_key = os.environ.get("AUTH_HMAC_KEY")
    if not aes or not hmac_key:
        raise RuntimeError("AUTH_AES_KEY / AUTH_HMAC_KEY not set")
    return base64.b64decode(aes), base64.b64decode(hmac_key)


def seed_admin(
    email: str,
    name: str,
    password: str,
    *,
    force: bool = False,
    aes_key: bytes | None = None,
    hmac_key: bytes | None = None,
    connection_factory: _ConnectionFactory | None = None,
) -> tuple[str, int | None]:
    """Returns ('created'|'updated'|'skipped', user_id|None)."""
    if aes_key is None or hmac_key is None:
        aes_key, hmac_key = _load_keys()

    norm_email = email.strip().lower().encode()
    email_hmac = hmac_sha256(norm_email, hmac_key)
    email_enc = aes_gcm_encrypt(email.strip().encode(), aes_key)
    name_enc = aes_gcm_encrypt(name.encode(), aes_key)
    pw_hash = argon2_hash(password)

    cm = connection_factory() if connection_factory else _default_cm()
    with cm as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email_hmac = %s", (email_hmac,))
            row = cur.fetchone()
            if row:
                if not force:
                    return "skipped", row["id"]
                cur.execute(
                    "UPDATE users SET password_hash = %s, name_enc = %s, "
                    "is_admin = TRUE, failed_login_count = 0, locked_until = NULL "
                    "WHERE id = %s",
                    (pw_hash, name_enc, row["id"]),
                )
                conn.commit()
                return "updated", row["id"]
            cur.execute(
                "INSERT INTO users (email_enc, email_hmac, name_enc, password_hash, is_admin) "
                "VALUES (%s, %s, %s, %s, TRUE)",
                (email_enc, email_hmac, name_enc, pw_hash),
            )
            new_id = cur.lastrowid
        conn.commit()
        return "created", new_id


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Seed initial admin user")
    p.add_argument("--force", action="store_true", help="기존 계정 덮어쓰기")
    args = p.parse_args(argv)

    email = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip()
    name = os.environ.get("INITIAL_ADMIN_NAME", "Admin").strip() or "Admin"
    password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
    if not email or not password:
        print(
            "ERROR: INITIAL_ADMIN_EMAIL / INITIAL_ADMIN_PASSWORD env required",
            file=sys.stderr,
        )
        return 1

    action, uid = seed_admin(email, name, password, force=args.force)
    # 이메일 원문 출력 지양 → 이벤트만
    print(f"{action}: admin user id={uid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
