"""Funções utilitárias compartilhadas."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


def seconds_to_timestamp(seconds: float, milliseconds: bool = False) -> str:
    seconds = max(0.0, float(seconds))
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    if milliseconds:
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def stable_output_key(media: Path, input_root: Path | None = None) -> str:
    """Nome legível, com hash quando uma raiz de lote pode gerar colisões."""
    if input_root is None or input_root.is_file():
        return media.stem
    relative = media.resolve().relative_to(input_root.resolve())
    digest = hashlib.sha256(relative.as_posix().casefold().encode("utf-8")).hexdigest()[:10]
    return f"{media.stem}__{digest}"


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

