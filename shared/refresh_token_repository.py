"""refresh_tokens 테이블 DAO.

단일 세션: user_id PK → 사용자당 1개 refresh 만 유효.
rotation: 재사용 감지를 위해 직전 hash 를 rotated_from 에 기록.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pymysql.connections import Connection


@dataclass
class RefreshTokenRow:
    user_id: int
    token_hash: str
    issued_at: datetime
    expires_at: datetime
    rotated_from: str | None

    @classmethod
    def from_row(cls, row: dict) -> "RefreshTokenRow":
        return cls(
            user_id=row["user_id"],
            token_hash=row["token_hash"],
            issued_at=row["issued_at"],
            expires_at=row["expires_at"],
            rotated_from=row.get("rotated_from"),
        )


class RefreshTokenRepository:
    _COLS = "user_id, token_hash, issued_at, expires_at, rotated_from"

    def __init__(self, conn: Connection):
        self.conn = conn

    def upsert(
        self,
        *,
        user_id: int,
        token_hash: str,
        issued_at: datetime,
        expires_at: datetime,
        rotated_from: str | None = None,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO refresh_tokens "
                "(user_id, token_hash, issued_at, expires_at, rotated_from) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "token_hash = VALUES(token_hash), "
                "issued_at = VALUES(issued_at), "
                "expires_at = VALUES(expires_at), "
                "rotated_from = VALUES(rotated_from)",
                (user_id, token_hash, issued_at, expires_at, rotated_from),
            )
        self.conn.commit()

    def find_by_user(self, user_id: int) -> RefreshTokenRow | None:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._COLS} FROM refresh_tokens WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
        return RefreshTokenRow.from_row(row) if row else None

    def delete_by_user(self, user_id: int) -> None:
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user_id,))
        self.conn.commit()
