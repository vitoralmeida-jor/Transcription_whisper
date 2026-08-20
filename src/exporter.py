"""Exportadores TXT, JSON e SRT com escrita atômica."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .config import OutputConfig
from .models import AlignedSegment
from .utils import atomic_write_text, seconds_to_timestamp


def output_paths(root: Path, key: str, config: OutputConfig) -> dict[str, Path]:
    enabled = {"txt": config.txt, "json": config.json, "srt": config.srt}
    return {kind: root / kind / f"{key}.{kind}" for kind, active in enabled.items() if active}


def outputs_complete(root: Path, key: str, config: OutputConfig) -> bool:
    paths = output_paths(root, key, config)
    return bool(paths) and all(path.is_file() and path.stat().st_size > 0 for path in paths.values())


def export_all(
    output_root: Path,
    key: str,
    source: Path,
    language: str,
    duration: float,
    model: str,
    diarization: bool,
    segments: list[AlignedSegment],
    config: OutputConfig,
) -> dict[str, Path]:
    paths = output_paths(output_root, key, config)
    if "txt" in paths:
        atomic_write_text(paths["txt"], render_txt(source, language, duration, segments))
    if "json" in paths:
        atomic_write_text(
            paths["json"],
            render_json(source, language, duration, model, diarization, segments),
        )
    if "srt" in paths:
        atomic_write_text(paths["srt"], render_srt(segments))
    return paths


def _paragraphs(segments: list[AlignedSegment]) -> list[AlignedSegment]:
    """Agrupa falas contíguas do mesmo falante apenas para o TXT."""
    grouped: list[AlignedSegment] = []
    for item in segments:
        if grouped and grouped[-1].speaker == item.speaker and item.start - grouped[-1].end <= 1.5:
            previous = grouped[-1]
            grouped[-1] = AlignedSegment(
                previous.start, item.end, f"{previous.text.rstrip()} {item.text.lstrip()}", item.speaker
            )
        else:
            grouped.append(item)
    return grouped


def render_txt(source: Path, language: str, duration: float, segments: list[AlignedSegment]) -> str:
    lines = [
        f"ARQUIVO: {source.name}", f"IDIOMA: {language}",
        f"DURAÇÃO: {seconds_to_timestamp(duration)}", "", "=" * 40, "",
    ]
    for item in _paragraphs(segments):
        label = f" {item.speaker}" if item.speaker else ""
        lines.extend([f"[{seconds_to_timestamp(item.start)}]{label}", item.text.strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_json(
    source: Path, language: str, duration: float, model: str,
    diarization: bool, segments: list[AlignedSegment],
) -> str:
    entries = []
    for index, item in enumerate(segments, 1):
        entry = asdict(item)
        entry.update(
            id=index,
            start=round(item.start, 3), end=round(item.end, 3),
            start_timestamp=seconds_to_timestamp(item.start),
            end_timestamp=seconds_to_timestamp(item.end),
        )
        entries.append(entry)
    data = {
        "metadata": {
            "file": source.name, "source_path": str(source), "language": language,
            "duration_seconds": round(duration, 3), "whisper_model": model,
            "diarization": diarization,
        },
        "full_text": " ".join(item.text.strip() for item in segments),
        "segments": entries,
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def render_srt(segments: list[AlignedSegment]) -> str:
    blocks = []
    for index, item in enumerate(segments, 1):
        speaker = f"[{item.speaker}] " if item.speaker else ""
        blocks.append(
            f"{index}\n{seconds_to_timestamp(item.start, True)} --> "
            f"{seconds_to_timestamp(item.end, True)}\n{speaker}{item.text.strip()}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")

