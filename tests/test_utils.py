from pathlib import Path

import pytest

from src.utils import seconds_to_timestamp, stable_output_key


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "00:00:00"), (65.9, "00:01:05"), (3661, "01:01:01"), (-1, "00:00:00")],
)
def test_readable_timestamp(seconds, expected):
    assert seconds_to_timestamp(seconds) == expected


def test_srt_timestamp_rounding():
    assert seconds_to_timestamp(3.210, milliseconds=True) == "00:00:03,210"
    assert seconds_to_timestamp(59.9996, milliseconds=True) == "00:01:00,000"


def test_recursive_keys_avoid_same_name_collision(tmp_path: Path):
    first = tmp_path / "a" / "entrevista.mp4"
    second = tmp_path / "b" / "entrevista.mp4"
    first.parent.mkdir()
    second.parent.mkdir()
    first.touch()
    second.touch()
    assert stable_output_key(first, tmp_path) != stable_output_key(second, tmp_path)


def test_single_file_key_stays_readable(tmp_path: Path):
    media = tmp_path / "Entrevista Final.MP4"
    media.touch()
    assert stable_output_key(media) == "Entrevista Final"

