"""얼굴 인식 모듈 테스트.

face_recognition 라이브러리를 mock하여 실제 모델 로딩 없이 테스트한다.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# face_recognition 모듈 mock 설정 (최상위에서 sys.modules에 주입)
# ---------------------------------------------------------------------------

_mock_fr = MagicMock(name="face_recognition")
sys.modules.setdefault("face_recognition", _mock_fr)


from src.face.encoder import EncodingStore, NoFaceDetectedError, load_encodings, register  # noqa: E402
from src.face.filter import FaceFilter  # noqa: E402


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_encoding(seed: int = 0) -> np.ndarray:
    """재현 가능한 128-dim 인코딩 벡터를 생성한다."""
    rng = np.random.default_rng(seed)
    return rng.random(128).astype(np.float64)


# ---------------------------------------------------------------------------
# encoder.py 테스트
# ---------------------------------------------------------------------------


class TestLoadEncodings:
    def test_returns_empty_store_when_file_missing(self, tmp_path: Path) -> None:
        store = load_encodings(tmp_path / "nonexistent.pkl")
        assert isinstance(store, EncodingStore)
        assert store.entries == []

    def test_loads_existing_store(self, tmp_path: Path) -> None:
        enc = _make_encoding(1)
        original = EncodingStore(entries=[{"label": "alice", "encoding": enc}])
        pkl = tmp_path / "encodings.pkl"
        with pkl.open("wb") as f:
            pickle.dump(original, f)

        loaded = load_encodings(pkl)
        assert len(loaded.entries) == 1
        assert loaded.entries[0]["label"] == "alice"
        np.testing.assert_array_equal(loaded.entries[0]["encoding"], enc)

    def test_backwards_compat_list_format(self, tmp_path: Path) -> None:
        """이전 list 포맷도 로딩 가능해야 한다."""
        enc = _make_encoding(2)
        old_data = [{"label": "bob", "encoding": enc}]
        pkl = tmp_path / "encodings.pkl"
        with pkl.open("wb") as f:
            pickle.dump(old_data, f)

        loaded = load_encodings(pkl)
        assert len(loaded.entries) == 1
        assert loaded.entries[0]["label"] == "bob"


class TestRegister:
    def test_register_saves_encoding(self, tmp_path: Path) -> None:
        enc = _make_encoding(3)
        fake_image = tmp_path / "person.jpg"
        fake_image.touch()
        pkl = tmp_path / "encodings.pkl"

        with patch("src.face.encoder.face_recognition") as mock_fr:
            mock_fr.load_image_file.return_value = MagicMock()
            mock_fr.face_encodings.return_value = [enc]

            count = register(fake_image, label="carol", encodings_path=pkl)

        assert count == 1
        store = load_encodings(pkl)
        assert len(store.entries) == 1
        assert store.entries[0]["label"] == "carol"

    def test_register_multiple_faces(self, tmp_path: Path) -> None:
        encs = [_make_encoding(i) for i in range(3)]
        fake_image = tmp_path / "group.jpg"
        fake_image.touch()
        pkl = tmp_path / "encodings.pkl"

        with patch("src.face.encoder.face_recognition") as mock_fr:
            mock_fr.load_image_file.return_value = MagicMock()
            mock_fr.face_encodings.return_value = encs

            count = register(fake_image, label="group", encodings_path=pkl)

        assert count == 3
        store = load_encodings(pkl)
        assert len(store.entries) == 3

    def test_register_raises_when_no_face(self, tmp_path: Path) -> None:
        fake_image = tmp_path / "landscape.jpg"
        fake_image.touch()

        with patch("src.face.encoder.face_recognition") as mock_fr:
            mock_fr.load_image_file.return_value = MagicMock()
            mock_fr.face_encodings.return_value = []

            with pytest.raises(NoFaceDetectedError):
                register(fake_image, encodings_path=tmp_path / "enc.pkl")

    def test_register_raises_when_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            register(tmp_path / "ghost.jpg", encodings_path=tmp_path / "enc.pkl")

    def test_register_accumulates_entries(self, tmp_path: Path) -> None:
        """두 번 등록하면 인코딩이 누적되어야 한다."""
        enc_a = _make_encoding(10)
        enc_b = _make_encoding(11)
        img_a = tmp_path / "a.jpg"
        img_b = tmp_path / "b.jpg"
        img_a.touch()
        img_b.touch()
        pkl = tmp_path / "enc.pkl"

        with patch("src.face.encoder.face_recognition") as mock_fr:
            mock_fr.load_image_file.return_value = MagicMock()
            mock_fr.face_encodings.return_value = [enc_a]
            register(img_a, label="dave", encodings_path=pkl)

        with patch("src.face.encoder.face_recognition") as mock_fr:
            mock_fr.load_image_file.return_value = MagicMock()
            mock_fr.face_encodings.return_value = [enc_b]
            register(img_b, label="eve", encodings_path=pkl)

        store = load_encodings(pkl)
        assert len(store.entries) == 2
        labels = {e["label"] for e in store.entries}
        assert labels == {"dave", "eve"}


# ---------------------------------------------------------------------------
# filter.py 테스트
# ---------------------------------------------------------------------------


class TestFaceFilterIsMatch:
    def _make_store(self, tmp_path: Path, enc: np.ndarray, label: str = "ref") -> Path:
        pkl = tmp_path / "encodings.pkl"
        store = EncodingStore(entries=[{"label": label, "encoding": enc}])
        with pkl.open("wb") as f:
            pickle.dump(store, f)
        return pkl

    # -- 얼굴 미검출 → False (OI-01 정책) -----------------------------------

    def test_no_face_detected_returns_false(self, tmp_path: Path) -> None:
        enc = _make_encoding(0)
        pkl = self._make_store(tmp_path, enc)
        fake_image = tmp_path / "empty.jpg"
        fake_image.touch()

        ff = FaceFilter(tolerance=0.6, encodings_path=pkl)

        with patch("src.face.filter.face_recognition") as mock_fr:
            mock_fr.load_image_file.return_value = MagicMock()
            mock_fr.face_encodings.return_value = []

            result = ff.is_match(fake_image)

        assert result is False

    # -- 매칭 성공 → True ----------------------------------------------------

    def test_matching_face_returns_true(self, tmp_path: Path) -> None:
        enc = _make_encoding(5)
        pkl = self._make_store(tmp_path, enc)
        fake_image = tmp_path / "match.jpg"
        fake_image.touch()

        ff = FaceFilter(tolerance=0.6, encodings_path=pkl)

        with patch("src.face.filter.face_recognition") as mock_fr:
            mock_fr.load_image_file.return_value = MagicMock()
            mock_fr.face_encodings.return_value = [enc]
            mock_fr.compare_faces.return_value = [True]

            result = ff.is_match(fake_image)

        assert result is True

    # -- 매칭 실패 → False ---------------------------------------------------

    def test_non_matching_face_returns_false(self, tmp_path: Path) -> None:
        enc_ref = _make_encoding(6)
        enc_unknown = _make_encoding(99)
        pkl = self._make_store(tmp_path, enc_ref)
        fake_image = tmp_path / "stranger.jpg"
        fake_image.touch()

        ff = FaceFilter(tolerance=0.6, encodings_path=pkl)

        with patch("src.face.filter.face_recognition") as mock_fr:
            mock_fr.load_image_file.return_value = MagicMock()
            mock_fr.face_encodings.return_value = [enc_unknown]
            mock_fr.compare_faces.return_value = [False]

            result = ff.is_match(fake_image)

        assert result is False

    # -- tolerance 적용 테스트 -----------------------------------------------

    def test_tolerance_is_passed_to_compare_faces(self, tmp_path: Path) -> None:
        enc = _make_encoding(7)
        pkl = self._make_store(tmp_path, enc)
        fake_image = tmp_path / "img.jpg"
        fake_image.touch()

        custom_tolerance = 0.4
        ff = FaceFilter(tolerance=custom_tolerance, encodings_path=pkl)

        with patch("src.face.filter.face_recognition") as mock_fr:
            mock_fr.load_image_file.return_value = MagicMock()
            mock_fr.face_encodings.return_value = [enc]
            mock_fr.compare_faces.return_value = [True]

            ff.is_match(fake_image)

            assert mock_fr.compare_faces.call_count == 1
            call_args, call_kwargs = mock_fr.compare_faces.call_args
            # numpy 배열 직접 비교
            known_list, unknown_enc = call_args
            assert call_kwargs.get("tolerance") == pytest.approx(custom_tolerance)
            assert len(known_list) == 1
            np.testing.assert_array_equal(known_list[0], enc)
            np.testing.assert_array_equal(unknown_enc, enc)

    # -- 복수 얼굴: 하나라도 매칭되면 True -----------------------------------

    def test_multiple_faces_one_match_returns_true(self, tmp_path: Path) -> None:
        enc_ref = _make_encoding(8)
        enc_stranger = _make_encoding(88)
        pkl = self._make_store(tmp_path, enc_ref)
        fake_image = tmp_path / "multi.jpg"
        fake_image.touch()

        ff = FaceFilter(tolerance=0.6, encodings_path=pkl)

        with patch("src.face.filter.face_recognition") as mock_fr:
            mock_fr.load_image_file.return_value = MagicMock()
            mock_fr.face_encodings.return_value = [enc_stranger, enc_ref]
            # 첫 번째 얼굴(stranger)은 불일치, 두 번째(ref)는 일치
            mock_fr.compare_faces.side_effect = [[False], [True]]

            result = ff.is_match(fake_image)

        assert result is True

    # -- 복수 얼굴: 모두 불일치 → False --------------------------------------

    def test_multiple_faces_no_match_returns_false(self, tmp_path: Path) -> None:
        enc_ref = _make_encoding(9)
        pkl = self._make_store(tmp_path, enc_ref)
        fake_image = tmp_path / "multi_no_match.jpg"
        fake_image.touch()

        ff = FaceFilter(tolerance=0.6, encodings_path=pkl)

        with patch("src.face.filter.face_recognition") as mock_fr:
            mock_fr.load_image_file.return_value = MagicMock()
            mock_fr.face_encodings.return_value = [_make_encoding(91), _make_encoding(92)]
            mock_fr.compare_faces.side_effect = [[False], [False]]

            result = ff.is_match(fake_image)

        assert result is False

    # -- 기준 인코딩 없음 → False --------------------------------------------

    def test_empty_store_returns_false(self, tmp_path: Path) -> None:
        pkl = tmp_path / "empty.pkl"
        store = EncodingStore()
        with pkl.open("wb") as f:
            pickle.dump(store, f)

        fake_image = tmp_path / "img.jpg"
        fake_image.touch()
        ff = FaceFilter(encodings_path=pkl)

        with patch("src.face.filter.face_recognition"):
            result = ff.is_match(fake_image)

        assert result is False

    # -- from_config 팩토리 --------------------------------------------------

    def test_from_config_reads_tolerance(self, tmp_path: Path) -> None:
        mock_config = MagicMock()
        mock_config.face.tolerance = 0.45

        ff = FaceFilter.from_config(mock_config)
        assert ff._tolerance == pytest.approx(0.45)
