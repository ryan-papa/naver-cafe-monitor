"""얼굴 인식 필터 모듈.

등록된 기준 인코딩과 이미지를 비교하여 매칭 여부를 반환한다.
DeepFace(Facenet512) 인코딩의 코사인 유사도를 사용한다.

OI-01 임시 정책:
- 얼굴 미검출 시 False 반환 (스킵)
- 복수 얼굴 검출 시 하나라도 매칭되면 True
"""
from __future__ import annotations

import logging
from pathlib import Path

from deepface import DeepFace
import numpy as np

from src.face.encoder import EncodingStore, _MODEL_NAME, load_encodings

logger = logging.getLogger(__name__)

# Facenet512 코사인 유사도 기본 threshold
_DEFAULT_THRESHOLD = 0.30


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """두 벡터의 코사인 유사도를 반환한다."""
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(dot / norm)


class FaceFilter:
    """기준 인코딩과 이미지 내 얼굴을 비교하는 필터."""

    def __init__(
        self,
        threshold: float = _DEFAULT_THRESHOLD,
        encodings_path: Path | None = None,
    ) -> None:
        """초기화.

        Args:
            threshold: 코사인 유사도 매칭 임계값 (높을수록 엄격, 기본값 0.30)
            encodings_path: 기준 인코딩 JSON 경로 (None이면 기본 경로 사용)
        """
        self._threshold = threshold
        self._encodings_path = encodings_path

    @classmethod
    def from_config(cls, config: object, encodings_path: Path | None = None) -> "FaceFilter":
        """Config 객체로부터 FaceFilter를 생성한다.

        Args:
            config: src.config.Config 인스턴스
            encodings_path: 기준 인코딩 JSON 경로 오버라이드

        Returns:
            FaceFilter 인스턴스
        """
        threshold = getattr(getattr(config, "face", None), "threshold", _DEFAULT_THRESHOLD)
        return cls(threshold=threshold, encodings_path=encodings_path)

    def _load_store(self) -> EncodingStore:
        return load_encodings(self._encodings_path)

    def is_match(self, image_path: str | Path) -> bool:
        """이미지에서 얼굴을 검출하고 기준 인코딩과 비교한다.

        Args:
            image_path: 비교할 이미지 경로

        Returns:
            기준 얼굴과 하나라도 매칭되면 True, 그 외 False
        """
        image_path = Path(image_path)
        store = self._load_store()

        if not store.entries:
            logger.warning("등록된 기준 인코딩이 없습니다. False 반환.")
            return False

        try:
            representations = DeepFace.represent(
                img_path=str(image_path),
                model_name=_MODEL_NAME,
                enforce_detection=True,
            )
        except ValueError:
            logger.debug("얼굴 미검출 (OI-01 정책: 스킵) — %s", image_path)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("이미지 로딩 실패: %s — %s", image_path, exc)
            return False

        if not representations:
            logger.debug("얼굴 미검출 (OI-01 정책: 스킵) — %s", image_path)
            return False

        unknown_encodings = [
            np.array(r["embedding"], dtype=np.float64) for r in representations
        ]
        known_encodings = [entry["encoding"] for entry in store.entries]

        for unknown_enc in unknown_encodings:
            for known_enc in known_encodings:
                sim = _cosine_similarity(unknown_enc, known_enc)
                if sim >= self._threshold:
                    return True

        return False
