"""Backend desacoplado de diarização com pyannote.audio."""

from __future__ import annotations

import os
from pathlib import Path

from .config import DiarizationConfig
from .models import SpeakerTurn


class DiarizationError(RuntimeError):
    """Falha ao carregar ou executar o backend de diarização."""


class PyannoteDiarizer:
    def __init__(self, config: DiarizationConfig):
        self.config = config
        self._pipeline = None

    def _load(self):
        if self._pipeline is not None:
            return self._pipeline
        try:
            import torch
            from dotenv import load_dotenv
            from pyannote.audio import Pipeline
        except ImportError as exc:
            raise DiarizationError(
                "pyannote.audio não está instalado. Execute: pip install -r requirements.txt"
            ) from exc
        load_dotenv()
        source = str(self.config.local_model_path or self.config.model)
        token = os.getenv("HF_TOKEN") or None
        try:
            self._pipeline = Pipeline.from_pretrained(source, token=token)
            self._pipeline.to(torch.device(self.config.device))
        except Exception as exc:
            raise DiarizationError(
                "Não foi possível carregar o pyannote. Aceite os termos do modelo, "
                "configure HF_TOKEN para o primeiro download ou use local_model_path. "
                f"Detalhe: {exc}"
            ) from exc
        return self._pipeline

    def diarize(self, audio: Path) -> list[SpeakerTurn]:
        pipeline = self._load()
        options: dict[str, int] = {}
        if self.config.num_speakers is not None:
            options["num_speakers"] = self.config.num_speakers
        else:
            if self.config.min_speakers is not None:
                options["min_speakers"] = self.config.min_speakers
            if self.config.max_speakers is not None:
                options["max_speakers"] = self.config.max_speakers
        try:
            output = pipeline(str(audio), **options)
            annotation = getattr(output, "exclusive_speaker_diarization", None)
            if annotation is None:
                annotation = getattr(output, "speaker_diarization", output)
            return _annotation_to_turns(annotation)
        except Exception as exc:
            raise DiarizationError(f"Falha durante a diarização: {exc}") from exc


def _annotation_to_turns(annotation) -> list[SpeakerTurn]:
    turns: list[SpeakerTurn] = []
    if hasattr(annotation, "itertracks"):
        iterator = ((turn, speaker) for turn, _, speaker in annotation.itertracks(yield_label=True))
    else:
        iterator = iter(annotation)
    for turn, speaker in iterator:
        turns.append(SpeakerTurn(float(turn.start), float(turn.end), str(speaker)))
    return sorted(turns, key=lambda item: (item.start, item.end, item.speaker))

