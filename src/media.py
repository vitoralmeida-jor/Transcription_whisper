"""Descoberta, inspeção e preparação de mídia com FFmpeg."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"})
AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"})
SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


class MediaError(RuntimeError):
    """Falha na leitura ou conversão de mídia."""


@dataclass
class PreparedAudio:
    path: Path
    temporary: bool

    def cleanup(self) -> None:
        if self.temporary:
            self.path.unlink(missing_ok=True)


def is_supported(path: Path) -> bool:
    return path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS


def discover_media(path: Path, recursive: bool = False) -> list[Path]:
    path = path.expanduser().resolve()
    if not path.exists():
        raise MediaError(f"Caminho não encontrado: {path}")
    if path.is_file():
        if not is_supported(path):
            raise MediaError(f"Formato não suportado: {path.suffix or '(sem extensão)'}")
        return [path]
    iterator = path.rglob("*") if recursive else path.glob("*")
    return sorted((item for item in iterator if is_supported(item)), key=lambda p: str(p).casefold())


class MediaPreparer:
    def __init__(self, temp_dir: Path, sample_rate: int = 16000, channels: int = 1):
        self.temp_dir = temp_dir
        self.sample_rate = sample_rate
        self.channels = channels
        self.ffmpeg = shutil.which("ffmpeg")
        self.ffprobe = shutil.which("ffprobe")

    @property
    def available(self) -> bool:
        return bool(self.ffmpeg and self.ffprobe)

    def _probe(self, path: Path) -> dict:
        if not self.ffprobe:
            raise MediaError("FFprobe não encontrado. Instale o FFmpeg ou configure o PATH.")
        command = [
            self.ffprobe, "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate,channels:format=duration",
            "-of", "json", str(path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise MediaError(f"FFprobe não conseguiu ler o arquivo: {result.stderr.strip()}")
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise MediaError("FFprobe retornou dados inválidos") from exc
        if not data.get("streams"):
            raise MediaError("O arquivo não contém uma faixa de áudio legível")
        return data

    def duration(self, path: Path) -> float:
        data = self._probe(path)
        try:
            return float(data.get("format", {}).get("duration", 0.0))
        except (TypeError, ValueError):
            return 0.0

    def prepare(self, source: Path, output_key: str) -> PreparedAudio:
        data = self._probe(source)
        stream = data["streams"][0]
        already_ready = (
            source.suffix.casefold() == ".wav"
            and stream.get("codec_name") == "pcm_s16le"
            and int(stream.get("sample_rate", 0)) == self.sample_rate
            and int(stream.get("channels", 0)) == self.channels
        )
        if already_ready:
            return PreparedAudio(source, temporary=False)
        if not self.ffmpeg:
            raise MediaError("FFmpeg não encontrado. Instale-o ou adicione o executável ao PATH.")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        target = self.temp_dir / f"{output_key}.wav"
        command = [
            self.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source), "-map", "0:a:0", "-vn", "-ac", str(self.channels),
            "-ar", str(self.sample_rate), "-c:a", "pcm_s16le", str(target),
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0 or not target.is_file():
            target.unlink(missing_ok=True)
            raise MediaError(f"FFmpeg não conseguiu preparar o áudio: {result.stderr.strip()}")
        return PreparedAudio(target, temporary=True)

