"""얼굴 인식 필터 모듈.

등록된 기준 인코딩과 이미지를 비교하여 매칭 여부를 반환한다.

OI-01 임시 정책:
- 얼굴 미검출 시 False 반환 (스킵)
- 복수 얼굴 검출 시 하나라도 매칭되면 True
"""
from __future__ import annotations

import logging
from pathlib import Path

import face_recognition

from src.face.encoder import EncodingStore, load_encodings

logger = logging.getLogger(__name__)

_DEFAULT_TOLERANCE = 0.6


class FaceFilter:
    """기준 인코딩과 이미지 내 얼굴을 비교하는 필터."""

    def __init__(
        self,
        tolerance: float = _DEFAULT_TOLERANCE,
        encodings_path: Path | None = None,
    ) -> None:
        """초기화.

        Args:
            tolerance: 얼굴 매칭 허용 거리 (낮을수록 엄격, 기본값 0.6)
            encodings_path: 기준 인코딩 pkl 경로 (None이면 기본 경로 사용)
        """
        self._tolerance = tolerance
        self._encodings_path = encodings_path

    @classmethod
    def from_config(cls, config: object, encodings_path: Path | None = None) -> "FaceFilter":
        """Config 객체로부터 FaceFilter를 생성한다.

        Args:
            config: src.config.Config 인스턴스
            encodings_path: 기준 인코딩 pkl 경로 오버라이드

        Returns:
            FaceFilter 인스턴스
        """
        tolerance = getattr(getattr(config, "face", None), "tolerance", _DEFAULT_TOLERANCE)
        return cls(tolerance=tolerance, encodings_path=encodings_path)

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
            image = face_recognition.load_image_file(str(image_path))
            unknown_encodings = face_recognition.face_encodings(image)
        except Exception as exc:  # noqa: BLE001
            logger.warning("이미지 로딩 실패: %s — %s", image_path, exc)
            return False

        if not unknown_encodings:
            logger.debug("얼굴 미검출 (OI-01 정책: 스킵) — %s", image_path)
            return False

        known_encodings = [entry["encoding"] for entry in store.entries]

        for unknown_enc in unknown_encodings:
            results = face_recognition.compare_faces(
                known_encodings, unknown_enc, tolerance=self._tolerance
            )
            if any(results):
                return True

        return False
