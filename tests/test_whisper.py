import pytest
from unittest.mock import patch, MagicMock
from whisper_transcribe import transcribe_audio, WhisperError

def test_raises_on_ytdlp_failure():
    with patch("whisper_transcribe.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        with pytest.raises(WhisperError):
            transcribe_audio("abc123", model="medium", tmp_dir="/tmp")

def test_cleans_up_audio_on_success(tmp_path):
    audio_file = tmp_path / "abc123.mp3"
    audio_file.write_text("fake")

    mock_result = {"text": "Hello world", "language": "en"}

    with patch("whisper_transcribe.subprocess.run") as mock_run, \
         patch("whisper_transcribe.whisper") as mock_whisper, \
         patch("whisper_transcribe._find_audio", return_value=str(audio_file)):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mock_model = MagicMock()
        mock_model.transcribe.return_value = mock_result
        mock_whisper.load_model.return_value = mock_model

        text, lang = transcribe_audio("abc123", model="medium", tmp_dir=str(tmp_path))

    assert text == "Hello world"
    assert lang == "en"
    assert not audio_file.exists()  # cleaned up
