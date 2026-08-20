import pytest

from src.aligner import UNKNOWN_SPEAKER, align_segments, overlap, without_diarization
from src.models import SpeakerTurn, TranscriptSegment


def test_overlap():
    assert overlap(10, 15, 10, 10.8) == pytest.approx(0.8)
    assert overlap(10, 15, 10.8, 15) == pytest.approx(4.2)
    assert overlap(0, 1, 2, 3) == 0


def test_largest_total_overlap_wins():
    transcript = [TranscriptSegment(10, 15, "Decisão tomada ontem.")]
    turns = [SpeakerTurn(10, 10.8, "SPEAKER_00"), SpeakerTurn(10.8, 15, "SPEAKER_01")]
    assert align_segments(transcript, turns)[0].speaker == "SPEAKER_01"


def test_multiple_turns_from_same_speaker_are_accumulated():
    transcript = [TranscriptSegment(0, 10, "Texto")]
    turns = [
        SpeakerTurn(0, 3, "SPEAKER_00"), SpeakerTurn(3, 6, "SPEAKER_01"),
        SpeakerTurn(6, 10, "SPEAKER_00"),
    ]
    assert align_segments(transcript, turns)[0].speaker == "SPEAKER_00"


def test_unknown_when_no_overlap():
    aligned = align_segments([TranscriptSegment(0, 1, "Oi")], [])
    assert aligned[0].speaker == UNKNOWN_SPEAKER


def test_no_diarization_has_null_speaker():
    assert without_diarization([TranscriptSegment(0, 1, "Oi")])[0].speaker is None
