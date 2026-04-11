"""얼굴 인코딩 등록/로딩 모듈.

face_recognition 라이브러리를 사용해 기준 이미지를 인코딩하고
data/faces/encodings.pkl에 저장한다.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import face_recognition

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_ENCODINGS_PATH = _PROJECT_ROOT / "data" / "faces" / "encodings.pkl"


@dataclass
class EncodingStore:
    """저장된 얼굴 인코딩 컬렉션."""

    entries: list[dict[str, Any]] = field(default_factory=list)


class NoFaceDetectedError(ValueError):
    """이미지에서 얼굴이 검출되지 않았을 때 발생하는 예외."""


def register(
    image_path: str | Path,
    label: str = "unknown",
    encodings_path: Path | None = None,
) -> int:
    """이미지에서 얼굴 인코딩을 추출하고 저장한다.

    Args:
        image_path: 기준 이미지 파일 경로
        label: 얼굴에 붙일 레이블 (이름 등)
        encodings_path: 저장 대상 pkl 파일 경로 (기본값: data/faces/encodings.pkl)

    Returns:
        저장된 얼굴 수

    Raises:
        FileNotFoundError: 이미지 파일이 없을 때
        NoFaceDetectedError: 이미지에서 얼굴을 찾지 못했을 때
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")

    save_path = encodings_path or _DEFAULT_ENCODINGS_PATH

    image = face_recognition.load_image_file(str(image_path))
    encodings = face_recognition.face_encodings(image)

    if not encodings:
        raise NoFaceDetectedError(
            f"이미지에서 얼굴을 검출하지 못했습니다: {image_path}"
        )

    store = load_encodings(save_path)
    for enc in encodings:
        store.entries.append({"label": label, "encoding": enc})

    save_path.parent.mkdir(parents=True, exist_ok=True)
    with save_path.open("wb") as f:
        pickle.dump(store, f)

    return len(encodings)


def load_encodings(encodings_path: Path | None = None) -> EncodingStore:
    """저장된 인코딩을 로딩한다.

    Args:
        encodings_path: pkl 파일 경로 (기본값: data/faces/encodings.pkl)

    Returns:
        EncodingStore 인스턴스 (파일 없으면 빈 스토어 반환)
    """
    path = encodings_path or _DEFAULT_ENCODINGS_PATH
    if not path.exists():
        return EncodingStore()

    with path.open("rb") as f:
        data = pickle.load(f)  # noqa: S301

    if isinstance(data, EncodingStore):
        return data

    # 이전 포맷(list) 호환
    if isinstance(data, list):
        return EncodingStore(entries=data)

    return EncodingStore()
