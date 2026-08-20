"""Backend de transcrição whisper.cpp."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

from .config import WhisperConfig
from .models import TranscriptSegment


class TranscriptionError(RuntimeError):
    """Falha de configuração ou execução do whisper.cpp."""


class WhisperCppTranscriber:
    def __init__(self, config: WhisperConfig, models_dir: Path, temp_dir: Path):
        self.config = config
        self.models_dir = models_dir
        self.temp_dir = temp_dir
        self.logger = logging.getLogger(__name__)

    @property
    def executable(self) -> Path:
        return self.config.executable

    @property
    def model_path(self) -> Path:
        value = Path(self.config.model).expanduser()
        if value.suffix.casefold() == ".bin" or value.is_absolute():
            return value if value.is_absolute() else (self.models_dir.parent.parent / value).resolve()
        return self.models_dir / f"ggml-{self.config.model}.bin"

    @property
    def available(self) -> bool:
        return self.executable.is_file() and self.model_path.is_file()

    def validate(self) -> list[str]:
        errors = []
        if not self.executable.is_file():
            errors.append(f"whisper.cpp não encontrado: {self.executable}")
        if not self.model_path.is_file():
            errors.append(f"modelo Whisper não encontrado: {self.model_path}")
        if self.config.use_gpu and self.config.gpu_backend.casefold() != "vulkan":
            errors.append("Esta configuração espera gpu_backend: vulkan")
        return errors

    def transcribe(self, audio: Path, output_key: str) -> list[TranscriptSegment]:
        errors = self.validate()
        if errors:
            raise TranscriptionError("; ".join(errors))
        prefix = self.temp_dir / f"{output_key}.whisper.{os.getpid()}"
        json_path = Path(f"{prefix}.json")
        command = [
            str(self.executable), "-m", str(self.model_path), "-f", str(audio),
            "-l", self.config.language, "-ojf", "-of", str(prefix), "-np",
        ]
        if not self.config.use_gpu:
            command.append("-ng")
        if self.config.threads > 0:
            command.extend(["-t", str(self.config.threads)])
        self.logger.info("Executando whisper.cpp | modelo=%s | gpu=%s", self.model_path, self.config.use_gpu)
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise TranscriptionError(f"whisper.cpp falhou: {(result.stderr or result.stdout).strip()}")
        if not json_path.is_file():
            raise TranscriptionError(f"whisper.cpp não gerou o JSON esperado: {json_path}")
        try:
            data = json.loads(json_path.read_text(encoding="utf-8-sig"))
            segments = parse_whisper_json(data)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise TranscriptionError(f"JSON inválido do whisper.cpp: {exc}") from exc
        finally:
            json_path.unlink(missing_ok=True)
        if not segments:
            raise TranscriptionError("whisper.cpp concluiu sem produzir segmentos")
        return segments


def parse_whisper_json(data: dict) -> list[TranscriptSegment]:
    transcription = data.get("transcription")
    if not isinstance(transcription, list):
        raise ValueError("campo 'transcription' ausente")
    result = []
    for item in transcription:
        offsets = item.get("offsets", {})
        start = float(offsets["from"]) / 1000.0
        end = float(offsets["to"]) / 1000.0
        text = str(item.get("text", "")).strip()
        if text and end >= start:
            result.append(TranscriptSegment(start=start, end=end, text=text))
    return result
