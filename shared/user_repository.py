"""users 테이블 DAO.

이메일 룩업은 email_hmac(=HMAC-SHA256(normalized_email, AUTH_HMAC_KEY)) 기준.
원문 이메일/이름은 AES-GCM 으로 암호화된 상태로 저장.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pymysql.connections import Connection


@dataclass
class UserRow:
    id: int
    email_enc: bytes
    email_hmac: bytes
    name_enc: bytes
    password_hash: str
    totp_secret_enc: bytes | None
    totp_enabled: bool
    backup_codes_hash: Any
    is_admin: bool
    failed_login_count: int
    locked_until: datetime | None

    @classmethod
    def from_row(cls, row: dict) -> "UserRow":
        return cls(
            id=row["id"],
            email_enc=row["email_enc"],
            email_hmac=row["email_hmac"],
            name_enc=row["name_enc"],
            password_hash=row["password_hash"],
            totp_secret_enc=row.get("totp_secret_enc"),
            totp_enabled=bool(row.get("totp_enabled")),
            backup_codes_hash=row.get("backup_codes_hash"),
            is_admin=bool(row.get("is_admin")),
            failed_login_count=row.get("failed_login_count", 0),
            locked_until=row.get("locked_until"),
        )


class UserRepository:
    _COLS = (
        "id, email_enc, email_hmac, name_enc, password_hash, "
        "totp_secret_enc, totp_enabled, backup_codes_hash, is_admin, "
        "failed_login_count, locked_until"
    )

    def __init__(self, conn: Connection):
        self.conn = conn

    def find_by_id(self, user_id: int) -> UserRow | None:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT {self._COLS} FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
        return UserRow.from_row(row) if row else None

    def find_by_email_hmac(self, email_hmac: bytes) -> UserRow | None:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._COLS} FROM users WHERE email_hmac = %s", (email_hmac,)
            )
            row = cur.fetchone()
        return UserRow.from_row(row) if row else None

    def increment_failed_login(self, user_id: int) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET failed_login_count = failed_login_count + 1 "
                "WHERE id = %s",
                (user_id,),
            )
        self.conn.commit()

    def reset_failed_login(self, user_id: int) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET failed_login_count = 0, locked_until = NULL "
                "WHERE id = %s",
                (user_id,),
            )
        self.conn.commit()

    def set_lock(self, user_id: int, locked_until: datetime) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET locked_until = %s WHERE id = %s",
                (locked_until, user_id),
            )
        self.conn.commit()

    def set_totp(self, user_id: int, totp_secret_enc: bytes, backup_codes_hash_json: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET totp_secret_enc = %s, backup_codes_hash = %s, "
                "totp_enabled = TRUE WHERE id = %s",
                (totp_secret_enc, backup_codes_hash_json, user_id),
            )
        self.conn.commit()

    def disable_totp(self, user_id: int) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET totp_secret_enc = NULL, backup_codes_hash = NULL, "
                "totp_enabled = FALSE WHERE id = %s",
                (user_id,),
            )
        self.conn.commit()

    def create(
        self,
        *,
        email_enc: bytes,
        email_hmac: bytes,
        name_enc: bytes,
        password_hash: str,
    ) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email_enc, email_hmac, name_enc, password_hash) "
                "VALUES (%s, %s, %s, %s)",
                (email_enc, email_hmac, name_enc, password_hash),
            )
            new_id = cur.lastrowid
        self.conn.commit()
        return new_id
