"""users 테이블 DAO.

이메일 룩업은 email_hmac(=HMAC-SHA256(normalized_email, AUTH_HMAC_KEY)) 기준.
원문 이메일/이름은 AES-GCM 으로 암호화된 상태로 저장.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pymysql.connections import Connection


@dataclass
class UserRow:
    id: int
    email_enc: bytes
    email_hmac: bytes
    name_enc: bytes
    password_hash: str
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
            is_admin=bool(row.get("is_admin")),
            failed_login_count=row.get("failed_login_count", 0),
            locked_until=row.get("locked_until"),
        )


class UserRepository:
    _COLS = (
        "id, email_enc, email_hmac, name_enc, password_hash, "
        "is_admin, failed_login_count, locked_until"
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

    def set_admin(self, user_id: int, is_admin: bool) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET is_admin = %s WHERE id = %s",
                (is_admin, user_id),
            )
        self.conn.commit()

    def create(
        self,
        *,
        email_enc: bytes,
        email_hmac: bytes,
        name_enc: bytes,
        password_hash: str,
        is_admin: bool = False,
    ) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email_enc, email_hmac, name_enc, password_hash, is_admin) "
                "VALUES (%s, %s, %s, %s, %s)",
                (email_enc, email_hmac, name_enc, password_hash, is_admin),
            )
            new_id = cur.lastrowid
        self.conn.commit()
        return new_id
