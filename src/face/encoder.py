"""얼굴 인코딩 등록/로딩 모듈.

face_recognition 라이브러리를 사용해 기준 이미지를 인코딩하고
data/faces/encodings.json에 저장한다.

보안 강화를 위해 pickle 대신 JSON 직렬화를 사용한다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import face_recognition
import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_ENCODINGS_PATH = _PROJECT_ROOT / "data" / "faces" / "encodings.json"


@dataclass
class EncodingStore:
    """저장된 얼굴 인코딩 컬렉션."""

    entries: list[dict[str, Any]] = field(default_factory=list)


class NoFaceDetectedError(ValueError):
    """이미지에서 얼굴이 검출되지 않았을 때 발생하는 예외."""


def _encoding_to_list(enc: Any) -> list[float]:
    """numpy array를 JSON 직렬화 가능한 리스트로 변환한다."""
    if isinstance(enc, np.ndarray):
        return enc.tolist()
    return list(enc)


def _list_to_encoding(lst: list[float]) -> np.ndarray:
    """리스트를 numpy array로 복원한다."""
    return np.array(lst, dtype=np.float64)


def register(
    image_path: str | Path,
    label: str = "unknown",
    encodings_path: Path | None = None,
) -> int:
    """이미지에서 얼굴 인코딩을 추출하고 저장한다.

    Args:
        image_path: 기준 이미지 파일 경로
        label: 얼굴에 붙일 레이블 (이름 등)
        encodings_path: 저장 대상 JSON 파일 경로 (기본값: data/faces/encodings.json)

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

    # JSON 직렬화: numpy array를 리스트로 변환하여 저장
    serializable = [
        {"label": e["label"], "encoding": _encoding_to_list(e["encoding"])}
        for e in store.entries
    ]
    save_path.write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return len(encodings)


def load_encodings(encodings_path: Path | None = None) -> EncodingStore:
    """저장된 인코딩을 로딩한다.

    Args:
        encodings_path: JSON 파일 경로 (기본값: data/faces/encodings.json)

    Returns:
        EncodingStore 인스턴스 (파일 없으면 빈 스토어 반환)
    """
    path = encodings_path or _DEFAULT_ENCODINGS_PATH
    if not path.exists():
        return EncodingStore()

    raw = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(raw, list):
        entries = [
            {"label": e["label"], "encoding": _list_to_encoding(e["encoding"])}
            for e in raw
        ]
        return EncodingStore(entries=entries)

    return EncodingStore()
