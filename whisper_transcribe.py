import subprocess, os, glob, time
import whisper

RETRY_DELAYS = [2, 4, 8]

class WhisperError(Exception):
    pass

def transcribe_audio(video_id: str, model: str, tmp_dir: str) -> tuple[str, str]:
    """
    Downloads audio for video_id into tmp_dir, transcribes with Whisper.
    Returns (transcript_text, language_code).
    Deletes audio file on success or failure.
    """
    audio_path = None
    try:
        audio_path = _download_audio(video_id, tmp_dir)
        return _transcribe(audio_path, model)
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)

def _download_audio(video_id: str, tmp_dir: str) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"
    out_template = os.path.join(tmp_dir, f"{video_id}.%(ext)s")
    last_exc = None

    attempts = [0] + RETRY_DELAYS
    for attempt, delay in enumerate(attempts):
        if delay:
            time.sleep(delay)
        proc = subprocess.run(
            ["yt-dlp", "-x", "--audio-format", "mp3", "-o", out_template, url],
            capture_output=True, text=True
        )
        if proc.returncode == 0:
            return _find_audio(tmp_dir, video_id)
        last_exc = proc.stderr.strip()
        if attempt == len(attempts) - 1:  # last attempt
            break

    raise WhisperError(f"yt-dlp download failed after retries: {last_exc}")

def _find_audio(tmp_dir: str, video_id: str) -> str:
    matches = glob.glob(os.path.join(tmp_dir, f"{video_id}.*"))
    if not matches:
        raise WhisperError(f"No audio file found for {video_id} in {tmp_dir}")
    # Sort by modification time descending (newest first) for determinism
    matches.sort(key=os.path.getmtime, reverse=True)
    return matches[0]

def _transcribe(audio_path: str, model_name: str) -> tuple[str, str]:
    try:
        model = whisper.load_model(model_name)
        result = model.transcribe(audio_path)
        text = result.get("text", "").strip()
        lang = result.get("language", None)
        return text, lang
    except Exception as e:
        raise WhisperError(f"Whisper transcription failed: {e}") from e
