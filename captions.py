import time
from youtube_transcript_api import YouTubeTranscriptApi as _YouTubeTranscriptApi
from youtube_transcript_api import TranscriptsDisabled, NoTranscriptFound

RETRY_DELAYS = [2, 4, 8]


class NoTranscriptError(Exception):
    pass


class YouTubeTranscriptApi:
    """Thin wrapper around the upstream YouTubeTranscriptApi that exposes
    ``list_transcripts`` as a class-level callable, making it easy to patch
    in tests while adapting to the new instance-based API."""

    @staticmethod
    def list_transcripts(video_id: str):
        return _YouTubeTranscriptApi().list(video_id)


def _segment_text(segment) -> str:
    """Extract text from a segment regardless of whether it is a dict or a
    FetchedTranscriptSnippet dataclass."""
    try:
        return segment["text"]
    except TypeError:
        return segment.text


def fetch_captions(video_id: str) -> tuple[str, str]:
    """
    Returns (transcript_text, language_code).
    Raises NoTranscriptError if unavailable after retries.
    """
    last_exc = None
    attempts = [0] + RETRY_DELAYS
    for attempt, delay in enumerate(attempts):
        if delay:
            time.sleep(delay)
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = _select_track(transcript_list)
            segments = transcript.fetch()
            text = " ".join(_segment_text(s) for s in segments)
            return text, transcript.language_code
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            raise NoTranscriptError(str(e)) from e
        except Exception as e:
            last_exc = e
            if attempt == len(attempts) - 1:  # last attempt
                break
    raise NoTranscriptError(f"Caption fetch failed after retries: {last_exc}") from last_exc


def _select_track(transcript_list):
    """Select best caption track per priority rules."""
    candidates = list(transcript_list)

    # 1. Manual English
    for t in candidates:
        if t.language_code == "en" and not t.is_generated:
            return t
    # 2. Auto-generated English
    for t in candidates:
        if t.language_code == "en" and t.is_generated:
            return t
    # 3. First manual any language
    for t in candidates:
        if not t.is_generated:
            return t
    # 4. First auto-generated any language
    if candidates:
        return candidates[0]
    raise NoTranscriptError("No caption tracks available")
