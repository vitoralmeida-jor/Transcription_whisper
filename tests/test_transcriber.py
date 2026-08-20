import pytest

from src.transcriber import parse_whisper_json


def test_parse_current_whisper_cpp_json():
    data = {
        "transcription": [
            {"offsets": {"from": 3210, "to": 11840}, "text": " Boa tarde. "}
        ]
    }
    segment = parse_whisper_json(data)[0]
    assert segment.start == 3.21
    assert segment.end == 11.84
    assert segment.text == "Boa tarde."


def test_missing_transcription_is_rejected():
    with pytest.raises(ValueError, match="transcription"):
        parse_whisper_json({})

