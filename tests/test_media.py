from pathlib import Path

import pytest

from src.media import MediaError, discover_media, is_supported


@pytest.mark.parametrize("name", ["a.mp4", "a.MKV", "a.mp3", "a.OpUs", "a.wav"])
def test_supported_extensions(tmp_path: Path, name: str):
    path = tmp_path / name
    path.touch()
    assert is_supported(path)


def test_unsupported_extension(tmp_path: Path):
    path = tmp_path / "notes.txt"
    path.touch()
    assert not is_supported(path)


def test_discovery_is_sorted_and_non_recursive_by_default(tmp_path: Path):
    (tmp_path / "z.mp3").touch()
    (tmp_path / "A.mp4").touch()
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "hidden.wav").touch()
    assert [p.name for p in discover_media(tmp_path)] == ["A.mp4", "z.mp3"]


def test_recursive_discovery(tmp_path: Path):
    nested = tmp_path / "sub"
    nested.mkdir()
    target = nested / "audio.flac"
    target.touch()
    assert discover_media(tmp_path, recursive=True) == [target.resolve()]


def test_missing_path_has_clear_error(tmp_path: Path):
    with pytest.raises(MediaError, match="Caminho não encontrado"):
        discover_media(tmp_path / "ausente")

