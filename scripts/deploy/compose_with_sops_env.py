#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def parse_dotenv(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    current_key: str | None = None
    current_value: list[str] = []

    for line in text.splitlines():
        if current_key is not None:
            current_value.append(line)
            if line.endswith("-----END PRIVATE KEY-----") or line.endswith("-----END PUBLIC KEY-----"):
                env[current_key] = "\n".join(current_value)
                current_key = None
                current_value = []
            continue

        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        if value.startswith("-----BEGIN ") and "-----END " not in value:
            current_key = key.strip()
            current_value = [value]
            continue
        env[key.strip()] = value

    if current_key is not None:
        env[current_key] = "\n".join(current_value)
    return env


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env.enc")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if not args.command:
        parser.error("command is required")

    env_file = Path(args.env_file)
    plain = subprocess.run(
        ["sops", "-d", "--input-type", "dotenv", "--output-type", "dotenv", str(env_file)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    env = os.environ.copy()
    env.update(parse_dotenv(plain))
    return subprocess.run(args.command, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
