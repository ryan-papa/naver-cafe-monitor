#!/usr/bin/env python3
"""Auth 시크릿 생성 (TA-01).

생성 대상:
- AUTH_RSA_PRIVATE_KEY / AUTH_RSA_PUBLIC_KEY : RSA-2048 keypair (E2E 필드 암호화)
- AUTH_AES_KEY                                : AES-256 (이메일/이름/TOTP secret 암호화)
- AUTH_HMAC_KEY                               : HMAC-SHA256 (이메일 룩업 인덱스)
- AUTH_JWT_SECRET                             : JWT 서명

생성 후 .env.enc 를 sops 로 재암호화한다. 기존 값이 있으면 `--force` 필요.
"""
from __future__ import annotations

import argparse
import base64
import io
import secrets
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

AUTH_KEYS: tuple[str, ...] = (
    "AUTH_RSA_PRIVATE_KEY",
    "AUTH_RSA_PUBLIC_KEY",
    "AUTH_AES_KEY",
    "AUTH_HMAC_KEY",
    "AUTH_JWT_SECRET",
)


def generate_rsa_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return priv_pem, pub_pem


def generate_b64_key(n_bytes: int = 32) -> str:
    return base64.b64encode(secrets.token_bytes(n_bytes)).decode()


def parse_dotenv(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env[key.strip()] = value
    return env


def render_dotenv(env: dict[str, str]) -> str:
    return "\n".join(f"{k}={v}" for k, v in env.items()) + "\n"


def sops_decrypt(env_enc: Path) -> str:
    result = subprocess.run(
        ["sops", "-d", str(env_enc)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def sops_encrypt(plain: str, env_enc: Path) -> None:
    tmp = env_enc.with_suffix(".enc.tmp")
    with tmp.open("w") as fp:
        subprocess.run(
            [
                "sops",
                "-e",
                "--input-type",
                "dotenv",
                "--output-type",
                "dotenv",
                "/dev/stdin",
            ],
            input=plain,
            text=True,
            check=True,
            stdout=fp,
        )
    tmp.replace(env_enc)


def escape_pem(pem: str) -> str:
    return pem.replace("\n", "\\n")


def build_auth_secrets() -> dict[str, str]:
    priv, pub = generate_rsa_keypair()
    return {
        "AUTH_RSA_PRIVATE_KEY": escape_pem(priv),
        "AUTH_RSA_PUBLIC_KEY": escape_pem(pub),
        "AUTH_AES_KEY": generate_b64_key(32),
        "AUTH_HMAC_KEY": generate_b64_key(32),
        "AUTH_JWT_SECRET": generate_b64_key(32),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auth 시크릿 생성 + .env.enc 업데이트")
    parser.add_argument("--env-enc", default=".env.enc", help="대상 .env.enc 경로")
    parser.add_argument("--force", action="store_true", help="기존 AUTH_* 키 덮어쓰기 허용")
    parser.add_argument("--dry-run", action="store_true", help="파일 변경 없이 미리보기만")
    args = parser.parse_args(argv)

    env_enc = Path(args.env_enc).resolve()
    if not env_enc.exists():
        print(f"ERROR: {env_enc} not found", file=sys.stderr)
        return 1

    plain = sops_decrypt(env_enc)
    env = parse_dotenv(plain)

    existing = [k for k in AUTH_KEYS if k in env]
    if existing and not args.force:
        print(f"ERROR: keys already exist: {existing}. Pass --force to overwrite.", file=sys.stderr)
        return 1

    secrets_map = build_auth_secrets()
    env.update(secrets_map)
    new_plain = render_dotenv(env)

    if args.dry_run:
        print("[dry-run] would write following keys:")
        for k in AUTH_KEYS:
            masked = secrets_map[k][:16] + "..."
            print(f"  {k} = {masked}")
        return 0

    sops_encrypt(new_plain, env_enc)
    print(f"OK: auth secrets written to {env_enc} ({len(AUTH_KEYS)} keys)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
