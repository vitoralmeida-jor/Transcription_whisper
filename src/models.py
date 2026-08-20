"""Estruturas de dados internas, independentes dos backends."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str


@dataclass(frozen=True)
class AlignedSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None

