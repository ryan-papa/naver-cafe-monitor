#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
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
    repo_dir = Path(__file__).resolve().parents[2]
    env_enc = repo_dir / ".env.enc"

    plain = subprocess.run(
        [
            "sops",
            "-d",
            "--input-type",
            "dotenv",
            "--output-type",
            "dotenv",
            str(env_enc),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    os.environ.update(parse_dotenv(plain))
    os.chdir(repo_dir)
    python_bin = str(repo_dir / ".venv/bin/python")
    os.execvp(
        python_bin,
        [
            python_bin,
            "-m",
            "uvicorn",
            "api.src.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
