"""MySQL 연결 모듈.

eepp.shop MySQL에 SSL 클라이언트 인증서 기반으로 접속한다.
batch와 api에서 공통으로 사용한다.
"""
from __future__ import annotations

import os
import ssl
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pymysql
from pymysql.connections import Connection
from dotenv import load_dotenv

_CERT_DIR = Path.home() / ".ssl" / "client-certs"
_DB_NAME = "naver_cafe_monitor"


def _build_ssl_context() -> ssl.SSLContext:
    """SSL 컨텍스트를 생성한다."""
    ca = _CERT_DIR / "ca-cert.pem"
    cert = _CERT_DIR / "client-cert.pem"
    key = _CERT_DIR / "client-key.pem"

    ctx = ssl.create_default_context(cafile=str(ca))
    ctx.load_cert_chain(certfile=str(cert), keyfile=str(key))
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def get_connection(
    host: str = "eepp.shop",
    port: int = 3306,
    user: str = "rp_readwrite",
    password: str | None = None,
    database: str = _DB_NAME,
) -> Connection:
    """MySQL 연결을 반환한다.

    password 미지정 시 환경변수 MYSQL_PASSWORD를 사용한다.
    """
    if password is None:
        load_dotenv()
        password = os.environ.get("MYSQL_PASSWORD", "")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        ssl=_build_ssl_context(),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=15,
        read_timeout=30,
    )


@contextmanager
def connect(
    host: str = "eepp.shop",
    port: int = 3306,
    user: str = "rp_readwrite",
    password: str | None = None,
    database: str = _DB_NAME,
) -> Generator[Connection, None, None]:
    """컨텍스트 매니저로 MySQL 연결을 관리한다.

    정상 종료 시 commit, 예외 시 rollback.
    """
    conn = get_connection(host=host, port=port, user=user, password=password, database=database)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
