"""얼굴 인식 모듈 테스트. DeepFace를 mock하여 실제 모델 로딩 없이 테스트한다."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# deepface 모듈 mock 설정
_mock_deepface = MagicMock(name="deepface")
_mock_DeepFace = MagicMock(name="deepface.DeepFace")
sys.modules.setdefault("deepface", _mock_deepface)
sys.modules.setdefault("deepface.DeepFace", _mock_DeepFace)
_mock_deepface.DeepFace = _mock_DeepFace

from src.face.encoder import EncodingStore, NoFaceDetectedError, load_encodings, register  # noqa: E402
from src.face.filter import FaceFilter, _cosine_similarity  # noqa: E402


def _enc(seed: int = 0) -> np.ndarray:
    """재현 가능한 512-dim 인코딩 벡터를 생성한다."""
    return np.random.default_rng(seed).random(512).astype(np.float64)


def _save(path: Path, entries: list[dict]) -> None:
    data = [
        {"label": e["label"], "encoding": e["encoding"].tolist()
         if isinstance(e["encoding"], np.ndarray) else list(e["encoding"])}
        for e in entries
    ]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _repr(enc: np.ndarray) -> dict:
    return {"embedding": enc.tolist(), "facial_area": {}, "face_confidence": 0.99}


# --- encoder.py ---

class TestLoadEncodings:
    def test_empty_when_missing(self, tmp_path: Path) -> None:
        store = load_encodings(tmp_path / "x.json")
        assert isinstance(store, EncodingStore) and store.entries == []

    def test_loads_existing(self, tmp_path: Path) -> None:
        e = _enc(1)
        p = tmp_path / "enc.json"
        _save(p, [{"label": "alice", "encoding": e}])
        loaded = load_encodings(p)
        assert len(loaded.entries) == 1 and loaded.entries[0]["label"] == "alice"
        np.testing.assert_array_almost_equal(loaded.entries[0]["encoding"], e)

    def test_loads_list_format(self, tmp_path: Path) -> None:
        p = tmp_path / "enc.json"
        _save(p, [{"label": "bob", "encoding": _enc(2)}])
        assert load_encodings(p).entries[0]["label"] == "bob"


class TestRegister:
    def test_saves_encoding(self, tmp_path: Path) -> None:
        e, img, jp = _enc(3), tmp_path / "p.jpg", tmp_path / "enc.json"
        img.touch()
        with patch("src.face.encoder.DeepFace") as m:
            m.represent.return_value = [_repr(e)]
            assert register(img, label="carol", encodings_path=jp) == 1
        store = load_encodings(jp)
        assert len(store.entries) == 1 and store.entries[0]["label"] == "carol"

    def test_multiple_faces(self, tmp_path: Path) -> None:
        encs = [_enc(i) for i in range(3)]
        img, jp = tmp_path / "g.jpg", tmp_path / "enc.json"
        img.touch()
        with patch("src.face.encoder.DeepFace") as m:
            m.represent.return_value = [_repr(e) for e in encs]
            assert register(img, label="group", encodings_path=jp) == 3
        assert len(load_encodings(jp).entries) == 3

    def test_raises_when_no_face(self, tmp_path: Path) -> None:
        img = tmp_path / "land.jpg"
        img.touch()
        with patch("src.face.encoder.DeepFace") as m:
            m.represent.side_effect = ValueError("no face")
            with pytest.raises(NoFaceDetectedError):
                register(img, encodings_path=tmp_path / "e.json")

    def test_raises_when_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            register(tmp_path / "ghost.jpg", encodings_path=tmp_path / "e.json")

    def test_accumulates(self, tmp_path: Path) -> None:
        a, b = tmp_path / "a.jpg", tmp_path / "b.jpg"
        a.touch(); b.touch()
        jp = tmp_path / "enc.json"
        with patch("src.face.encoder.DeepFace") as m:
            m.represent.return_value = [_repr(_enc(10))]
            register(a, label="dave", encodings_path=jp)
        with patch("src.face.encoder.DeepFace") as m:
            m.represent.return_value = [_repr(_enc(11))]
            register(b, label="eve", encodings_path=jp)
        store = load_encodings(jp)
        assert len(store.entries) == 2
        assert {e["label"] for e in store.entries} == {"dave", "eve"}


# --- filter.py ---

class TestCosineSimilarity:
    def test_identical(self) -> None:
        assert _cosine_similarity(_enc(42), _enc(42)) == pytest.approx(1.0)

    def test_orthogonal(self) -> None:
        assert _cosine_similarity(np.array([1., 0.]), np.array([0., 1.])) == pytest.approx(0.0)


class TestFaceFilterIsMatch:
    def _store(self, tmp: Path, e: np.ndarray, label: str = "ref") -> Path:
        p = tmp / "enc.json"
        _save(p, [{"label": label, "encoding": e}])
        return p

    def test_no_face_returns_false(self, tmp_path: Path) -> None:
        jp = self._store(tmp_path, _enc(0))
        img = tmp_path / "empty.jpg"; img.touch()
        ff = FaceFilter(threshold=0.30, encodings_path=jp)
        with patch("src.face.filter.DeepFace") as m:
            m.represent.side_effect = ValueError("no face")
            assert ff.is_match(img) is False

    def test_match_returns_true(self, tmp_path: Path) -> None:
        e = _enc(5)
        jp = self._store(tmp_path, e)
        img = tmp_path / "match.jpg"; img.touch()
        ff = FaceFilter(threshold=0.30, encodings_path=jp)
        with patch("src.face.filter.DeepFace") as m:
            m.represent.return_value = [_repr(e)]
            assert ff.is_match(img) is True

    def test_no_match_returns_false(self, tmp_path: Path) -> None:
        jp = self._store(tmp_path, _enc(6))
        img = tmp_path / "stranger.jpg"; img.touch()
        ff = FaceFilter(threshold=0.99, encodings_path=jp)
        with patch("src.face.filter.DeepFace") as m:
            m.represent.return_value = [_repr(_enc(99))]
            assert ff.is_match(img) is False

    def test_threshold_controls_matching(self, tmp_path: Path) -> None:
        e = _enc(7)
        jp = self._store(tmp_path, e)
        img = tmp_path / "img.jpg"; img.touch()
        ff = FaceFilter(threshold=0.5, encodings_path=jp)
        with patch("src.face.filter.DeepFace") as m:
            m.represent.return_value = [_repr(e)]
            assert ff.is_match(img) is True

    def test_multi_faces_one_match(self, tmp_path: Path) -> None:
        ref = _enc(8)
        jp = self._store(tmp_path, ref)
        img = tmp_path / "multi.jpg"; img.touch()
        ff = FaceFilter(threshold=0.99, encodings_path=jp)
        with patch("src.face.filter.DeepFace") as m:
            m.represent.return_value = [_repr(_enc(88)), _repr(ref)]
            assert ff.is_match(img) is True

    def test_multi_faces_no_match(self, tmp_path: Path) -> None:
        jp = self._store(tmp_path, _enc(9))
        img = tmp_path / "multi_no.jpg"; img.touch()
        ff = FaceFilter(threshold=0.9999, encodings_path=jp)
        with patch("src.face.filter.DeepFace") as m:
            m.represent.return_value = [_repr(_enc(91)), _repr(_enc(92))]
            assert ff.is_match(img) is False

    def test_empty_store_returns_false(self, tmp_path: Path) -> None:
        jp = tmp_path / "empty.json"
        jp.write_text("[]", encoding="utf-8")
        img = tmp_path / "img.jpg"; img.touch()
        assert FaceFilter(encodings_path=jp).is_match(img) is False

    def test_from_config_reads_threshold(self) -> None:
        cfg = MagicMock()
        cfg.face.threshold = 0.45
        assert FaceFilter.from_config(cfg)._threshold == pytest.approx(0.45)
