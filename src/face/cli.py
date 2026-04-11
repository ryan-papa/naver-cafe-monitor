"""얼굴 등록 CLI.

사용법:
    python -m src.face.cli register <image_path> [--label <name>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.face.encoder import NoFaceDetectedError, register

_DEFAULT_ENCODINGS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "faces" / "encodings.pkl"
)


def cmd_register(args: argparse.Namespace) -> int:
    """register 서브커맨드 처리."""
    image_path = Path(args.image_path)
    label = args.label or image_path.stem

    try:
        count = register(image_path, label=label)
    except FileNotFoundError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    except NoFaceDetectedError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    print(f"등록 완료:")
    print(f"  - 감지된 얼굴 수: {count}")
    print(f"  - 레이블: {label}")
    print(f"  - 저장 경로: {_DEFAULT_ENCODINGS_PATH}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.face.cli",
        description="얼굴 등록 CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    reg = subparsers.add_parser("register", help="이미지에서 얼굴을 등록한다")
    reg.add_argument("image_path", help="등록할 이미지 경로")
    reg.add_argument("--label", "-l", default=None, help="레이블(이름)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "register":
        return cmd_register(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
