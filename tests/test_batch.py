from pathlib import Path

from src.batch import Manifest


def test_manifest_recognizes_completed_unchanged_source(tmp_path: Path):
    source = tmp_path / "entrevista.mp4"
    source.write_bytes(b"media")
    manifest = Manifest(tmp_path / "output" / "manifest.json")
    manifest.update(source, "entrevista", "completed")

    reloaded = Manifest(manifest.path)
    assert reloaded.is_current(source, "entrevista")
    assert not reloaded.is_current(source, "outro-nome")


def test_manifest_detects_modified_source(tmp_path: Path):
    source = tmp_path / "entrevista.mp4"
    source.write_bytes(b"media")
    manifest = Manifest(tmp_path / "manifest.json")
    manifest.update(source, "entrevista", "completed")
    source.write_bytes(b"media alterada")
    assert not manifest.is_current(source, "entrevista")

