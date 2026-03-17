import pytest
from unittest.mock import patch, MagicMock
from captions import fetch_captions, NoTranscriptError

def make_segment(text):
    return {"text": text, "start": 0.0, "duration": 1.0}

def test_returns_joined_text():
    mock_transcript = MagicMock()
    mock_transcript.fetch.return_value = [make_segment("Hello"), make_segment("world")]
    mock_transcript.language_code = "en"
    mock_transcript.is_generated = False

    mock_list = MagicMock()
    mock_list.__iter__ = MagicMock(return_value=iter([mock_transcript]))
    mock_list.find_transcript.return_value = mock_transcript

    with patch("captions.YouTubeTranscriptApi.list_transcripts", return_value=mock_list):
        text, lang = fetch_captions("abc123")

    assert text == "Hello world"
    assert lang == "en"

def test_raises_no_transcript_when_unavailable():
    from youtube_transcript_api import TranscriptsDisabled
    with patch("captions.YouTubeTranscriptApi.list_transcripts", side_effect=TranscriptsDisabled("abc")):
        with pytest.raises(NoTranscriptError):
            fetch_captions("abc123")

def test_retries_on_429(monkeypatch):
    call_count = 0
    from youtube_transcript_api import TranscriptsDisabled

    def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("429")
        raise TranscriptsDisabled("abc")  # Eventually give up

    monkeypatch.setattr("captions.YouTubeTranscriptApi.list_transcripts", flaky)
    monkeypatch.setattr("captions.time.sleep", lambda x: None)

    with pytest.raises(NoTranscriptError):
        fetch_captions("abc123")

    assert call_count == 3
