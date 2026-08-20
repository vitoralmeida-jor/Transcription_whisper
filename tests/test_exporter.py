import json
from pathlib import Path

from src.config import OutputConfig
from src.exporter import export_all, outputs_complete, render_json, render_srt, render_txt
from src.models import AlignedSegment


SEGMENTS = [
    AlignedSegment(3.21, 11.84, "Boa tarde.", "SPEAKER_00"),
    AlignedSegment(12.05, 22.47, "Nós tivemos uma mudança.", "SPEAKER_01"),
]


def test_valid_srt():
    rendered = render_srt(SEGMENTS)
    assert "00:00:03,210 --> 00:00:11,840" in rendered
    assert "[SPEAKER_00] Boa tarde." in rendered
    assert rendered.endswith("\n")


def test_json_schema_and_unicode():
    data = json.loads(render_json(Path("entrevista.mp4"), "pt", 22.5, "large-v3", True, SEGMENTS))
    assert data["metadata"]["language"] == "pt"
    assert data["segments"][0]["start"] == 3.21
    assert data["segments"][0]["speaker"] == "SPEAKER_00"
    assert data["full_text"] == "Boa tarde. Nós tivemos uma mudança."


def test_txt_journalistic_layout():
    rendered = render_txt(Path("entrevista.mp4"), "pt", 60, SEGMENTS)
    assert "ARQUIVO: entrevista.mp4" in rendered
    assert "[00:00:03] SPEAKER_00" in rendered


def test_export_and_skip_detection(tmp_path: Path):
    config = OutputConfig()
    assert not outputs_complete(tmp_path, "entrevista", config)
    paths = export_all(
        tmp_path, "entrevista", Path("entrevista.mp4"), "pt", 22.5,
        "large-v3", True, SEGMENTS, config,
    )
    assert set(paths) == {"txt", "json", "srt"}
    assert outputs_complete(tmp_path, "entrevista", config)
    assert not list(tmp_path.rglob("*.tmp"))

