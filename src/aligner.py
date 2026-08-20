"""Alinhamento por maior sobreposição temporal."""

from __future__ import annotations

from collections import defaultdict

from .models import AlignedSegment, SpeakerTurn, TranscriptSegment


UNKNOWN_SPEAKER = "SPEAKER_UNKNOWN"


def overlap(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def align_segments(
    transcripts: list[TranscriptSegment], turns: list[SpeakerTurn]
) -> list[AlignedSegment]:
    """Atribui a cada segmento o falante com maior sobreposição acumulada.

    Um segmento do Whisper é mantido inteiro porque seus timestamps são de bloco,
    não limites confiáveis de palavras. O community-1 fornece diarização exclusiva,
    reduzindo empates e trocas artificiais.
    """
    aligned: list[AlignedSegment] = []
    for segment in transcripts:
        totals: dict[str, float] = defaultdict(float)
        for turn in turns:
            if turn.start >= segment.end:
                break
            if turn.end <= segment.start:
                continue
            totals[turn.speaker] += overlap(segment.start, segment.end, turn.start, turn.end)
        speaker = max(totals, key=totals.get) if totals else UNKNOWN_SPEAKER
        aligned.append(AlignedSegment(segment.start, segment.end, segment.text, speaker))
    return aligned


def without_diarization(transcripts: list[TranscriptSegment]) -> list[AlignedSegment]:
    return [AlignedSegment(item.start, item.end, item.text, None) for item in transcripts]

