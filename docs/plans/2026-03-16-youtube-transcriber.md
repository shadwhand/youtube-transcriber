# YouTube Transcriber Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that transcribes YouTube videos/playlists and a Claude skill that invokes it, summarizes results, and answers questions from the transcripts.

**Architecture:** A single `transcribe.py` script handles all mechanical work — URL resolution, caption fetching, Whisper fallback, DB storage, and summary querying. A Claude skill (`SKILL.md`) drives the script and reasons over results. No shared state between the two beyond the filesystem and SQLite DB.

**Tech Stack:** Python 3, `youtube-transcript-api`, `yt-dlp`, `openai-whisper` (+ PyTorch), `sqlite3` (stdlib), `argparse` (stdlib)

---

## File Structure

| File | Purpose |
|---|---|
| `~/Documents/youtube-transcriber/transcribe.py` | CLI entry point — argument parsing, orchestration |
| `~/Documents/youtube-transcriber/db.py` | DB init, read, write — all SQLite logic |
| `~/Documents/youtube-transcriber/captions.py` | Caption fetching via `youtube-transcript-api` with retry/backoff |
| `~/Documents/youtube-transcriber/whisper_transcribe.py` | Audio download via `yt-dlp` + Whisper transcription |
| `~/Documents/youtube-transcriber/resolver.py` | URL classification and video/playlist metadata resolution |
| `~/Documents/youtube-transcriber/summarize.py` | Extractive summary generation |
| `~/Documents/youtube-transcriber/tests/test_db.py` | DB tests |
| `~/Documents/youtube-transcriber/tests/test_captions.py` | Caption fetch + retry tests |
| `~/Documents/youtube-transcriber/tests/test_resolver.py` | URL classification tests |
| `~/Documents/youtube-transcriber/tests/test_summarize.py` | Summary generation tests |
| `~/Documents/youtube-transcriber/tests/test_transcribe.py` | Integration tests for CLI argument handling |
| `~/.claude/skills/yt-transcriber/SKILL.md` | Claude skill definition |

---

## Task 1: Project Setup

**Files:**
- Create: `~/Documents/youtube-transcriber/.venv/` (via shell)
- Create: `~/Documents/youtube-transcriber/requirements.txt`
- Create: `~/Documents/youtube-transcriber/tests/__init__.py`

- [ ] **Step 1: Create the venv and install dependencies**

```bash
cd ~/Documents/youtube-transcriber
python3 -m venv .venv
source .venv/bin/activate
pip install yt-dlp youtube-transcript-api openai-whisper pytest
```

Note: `openai-whisper` pulls in PyTorch — expect 1–3 GB download.

- [ ] **Step 2: Create `requirements.txt`**

```
yt-dlp
youtube-transcript-api
openai-whisper
pytest
```

Save to `~/Documents/youtube-transcriber/requirements.txt`.

- [ ] **Step 3: Create tests package**

```bash
mkdir -p ~/Documents/youtube-transcriber/tests
touch ~/Documents/youtube-transcriber/tests/__init__.py
```

- [ ] **Step 4: Verify pytest works**

```bash
cd ~/Documents/youtube-transcriber
source .venv/bin/activate
pytest tests/ -v
```

Expected: `no tests ran` (0 errors)

- [ ] **Step 5: Commit**

```bash
git init ~/Documents/youtube-transcriber
cd ~/Documents/youtube-transcriber
git add requirements.txt tests/__init__.py
git commit -m "chore: project setup"
```

---

## Task 2: DB Module

**Files:**
- Create: `~/Documents/youtube-transcriber/db.py`
- Create: `~/Documents/youtube-transcriber/tests/test_db.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_db.py
import os, tempfile, pytest
from db import init_db, insert_video, get_video, video_exists, get_summaries

@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "transcripts.db"
    conn = init_db(str(db_path))
    yield conn
    conn.close()

def test_init_creates_table(tmp_db):
    cur = tmp_db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='videos'")
    assert cur.fetchone() is not None

def test_video_not_exists_initially(tmp_db):
    assert not video_exists(tmp_db, "abc123")

def test_insert_and_exists(tmp_db):
    insert_video(tmp_db, {
        "video_id": "abc123", "title": "Test", "url": "https://youtube.com/watch?v=abc123",
        "playlist_id": None, "playlist_title": None, "language": "en",
        "method": "captions", "whisper_model": None,
        "summary": "First sentence.", "transcript_path": "/tmp/abc123.txt"
    })
    assert video_exists(tmp_db, "abc123")

def test_get_video_returns_row(tmp_db):
    insert_video(tmp_db, {
        "video_id": "abc123", "title": "Test", "url": "https://youtube.com/watch?v=abc123",
        "playlist_id": None, "playlist_title": None, "language": "en",
        "method": "captions", "whisper_model": None,
        "summary": "First sentence.", "transcript_path": "/tmp/abc123.txt"
    })
    row = get_video(tmp_db, "abc123")
    assert row["title"] == "Test"
    assert row["method"] == "captions"

def test_get_summaries_returns_matching_ids(tmp_db):
    insert_video(tmp_db, {
        "video_id": "id1", "title": "One", "url": "u1",
        "playlist_id": None, "playlist_title": None, "language": "en",
        "method": "captions", "whisper_model": None,
        "summary": "Summary one.", "transcript_path": "/tmp/id1.txt"
    })
    insert_video(tmp_db, {
        "video_id": "id2", "title": "Two", "url": "u2",
        "playlist_id": None, "playlist_title": None, "language": "en",
        "method": "captions", "whisper_model": None,
        "summary": "Summary two.", "transcript_path": "/tmp/id2.txt"
    })
    results = get_summaries(tmp_db, ["id1", "id999"])
    assert len(results) == 1
    assert results[0]["video_id"] == "id1"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd ~/Documents/youtube-transcriber && source .venv/bin/activate
pytest tests/test_db.py -v
```

Expected: `ImportError: No module named 'db'`

- [ ] **Step 3: Implement `db.py`**

```python
# db.py
import sqlite3
from datetime import datetime, timezone

def init_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            video_id      TEXT PRIMARY KEY,
            title         TEXT,
            url           TEXT,
            playlist_id   TEXT,
            playlist_title TEXT,
            language      TEXT,
            method        TEXT,
            whisper_model TEXT,
            summary       TEXT,
            transcribed_at TEXT,
            transcript_path TEXT
        )
    """)
    conn.commit()
    return conn

def video_exists(conn: sqlite3.Connection, video_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM videos WHERE video_id = ?", (video_id,)).fetchone()
    return row is not None

def insert_video(conn: sqlite3.Connection, data: dict) -> None:
    data = dict(data)
    data["transcribed_at"] = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO videos
        (video_id, title, url, playlist_id, playlist_title, language,
         method, whisper_model, summary, transcribed_at, transcript_path)
        VALUES
        (:video_id, :title, :url, :playlist_id, :playlist_title, :language,
         :method, :whisper_model, :summary, :transcribed_at, :transcript_path)
    """, data)
    conn.commit()

def get_video(conn: sqlite3.Connection, video_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,)).fetchone()

def get_summaries(conn: sqlite3.Connection, video_ids: list[str]) -> list[dict]:
    if not video_ids:
        return []
    placeholders = ",".join("?" * len(video_ids))
    rows = conn.execute(
        f"SELECT video_id, title, summary FROM videos WHERE video_id IN ({placeholders})",
        video_ids
    ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_db.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: DB module with init, insert, exists, query"
```

---

## Task 3: Summarize Module

**Files:**
- Create: `~/Documents/youtube-transcriber/summarize.py`
- Create: `~/Documents/youtube-transcriber/tests/test_summarize.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_summarize.py
from summarize import extract_summary

def test_extracts_three_sentences():
    text = "Hello world. This is a test. And a third. And a fourth."
    assert extract_summary(text) == "Hello world. This is a test. And a third."

def test_stops_at_500_chars():
    long_sentence = "A" * 300
    text = f"{long_sentence}. Short."
    result = extract_summary(text)
    assert len(result) <= 500

def test_handles_fewer_than_three_delimiters():
    text = "Only one sentence here"
    result = extract_summary(text)
    assert result == "Only one sentence here"

def test_handles_empty_string():
    assert extract_summary("") == ""

def test_exception_returns_none():
    assert extract_summary(None) is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_summarize.py -v
```

Expected: `ImportError: No module named 'summarize'`

- [ ] **Step 3: Implement `summarize.py`**

```python
# summarize.py
import re

def extract_summary(text: str | None) -> str | None:
    try:
        if not text:
            return text if text == "" else None
        # Lookbehind keeps the punctuation attached to the preceding token
        tokens = re.split(r'(?<=[.?!])\s', text)
        collected = []
        char_count = 0
        for token in tokens:
            if len(collected) >= 3 or char_count >= 500:
                break
            collected.append(token)
            char_count += len(token)
        return " ".join(collected)
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_summarize.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add summarize.py tests/test_summarize.py
git commit -m "feat: extractive summary module"
```

---

## Task 4: URL Resolver Module

**Files:**
- Create: `~/Documents/youtube-transcriber/resolver.py`
- Create: `~/Documents/youtube-transcriber/tests/test_resolver.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_resolver.py
from resolver import classify_url, VideoInfo, PlaylistInfo

def test_single_video_url():
    result = classify_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert isinstance(result, VideoInfo)
    assert result.video_id == "dQw4w9WgXcQ"

def test_playlist_url():
    result = classify_url("https://www.youtube.com/playlist?list=PLtest123")
    assert isinstance(result, PlaylistInfo)
    assert result.playlist_id == "PLtest123"

def test_combined_url_treated_as_playlist():
    result = classify_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLtest123")
    assert isinstance(result, PlaylistInfo)
    assert result.playlist_id == "PLtest123"

def test_short_url():
    result = classify_url("https://youtu.be/dQw4w9WgXcQ")
    assert isinstance(result, VideoInfo)
    assert result.video_id == "dQw4w9WgXcQ"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_resolver.py -v
```

Expected: `ImportError: No module named 'resolver'`

- [ ] **Step 3: Implement `resolver.py`**

```python
# resolver.py
import subprocess, json, sys
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs

@dataclass
class VideoInfo:
    video_id: str
    title: str = ""
    is_live: bool = False

@dataclass
class PlaylistInfo:
    playlist_id: str
    playlist_title: str = ""
    videos: list[VideoInfo] = None

    def __post_init__(self):
        if self.videos is None:
            self.videos = []

def classify_url(url: str) -> VideoInfo | PlaylistInfo:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    if "list" in qs:
        playlist_id = qs["list"][0]
        return PlaylistInfo(playlist_id=playlist_id)

    # youtu.be/<id> or watch?v=<id>
    if parsed.netloc == "youtu.be":
        video_id = parsed.path.lstrip("/")
    else:
        video_id = qs.get("v", [""])[0]

    return VideoInfo(video_id=video_id)

def resolve(url: str) -> VideoInfo | PlaylistInfo:
    """Classify URL and fetch metadata via yt-dlp."""
    classified = classify_url(url)

    if isinstance(classified, PlaylistInfo):
        result = _run_ytdlp(["--flat-playlist", "-J", url])
        data = json.loads(result)
        classified.playlist_title = data.get("title", "")
        classified.videos = [
            VideoInfo(
                video_id=e["id"],
                title=e.get("title", ""),
                is_live=e.get("live_status") in ("is_live", "is_upcoming")
            )
            for e in data.get("entries", [])
            if e.get("id")
        ]
        return classified
    else:
        result = _run_ytdlp(["-J", "--no-playlist", url])
        data = json.loads(result)
        classified.title = data.get("title", "")
        classified.is_live = data.get("live_status") in ("is_live", "is_upcoming")
        return classified

def _run_ytdlp(args: list[str]) -> str:
    cmd = ["yt-dlp"] + args
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {proc.stderr.strip()}")
    return proc.stdout
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_resolver.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add resolver.py tests/test_resolver.py
git commit -m "feat: URL resolver with video/playlist classification"
```

---

## Task 5: Captions Module

**Files:**
- Create: `~/Documents/youtube-transcriber/captions.py`
- Create: `~/Documents/youtube-transcriber/tests/test_captions.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_captions.py
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_captions.py -v
```

Expected: `ImportError: No module named 'captions'`

- [ ] **Step 3: Implement `captions.py`**

```python
# captions.py
import time
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

RETRY_DELAYS = [2, 4, 8]

class NoTranscriptError(Exception):
    pass

def fetch_captions(video_id: str) -> tuple[str, str]:
    """
    Returns (transcript_text, language_code).
    Raises NoTranscriptError if unavailable after retries.
    """
    last_exc = None
    for attempt, delay in enumerate([0] + RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = _select_track(transcript_list)
            segments = transcript.fetch()
            text = " ".join(s["text"] for s in segments)
            return text, transcript.language_code
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            raise NoTranscriptError(str(e)) from e
        except Exception as e:
            last_exc = e
            if attempt == len(RETRY_DELAYS):
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
    raise NoTranscriptFound(None, None)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_captions.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add captions.py tests/test_captions.py
git commit -m "feat: caption fetching with retry/backoff and track selection"
```

---

## Task 6: Whisper Module

**Files:**
- Create: `~/Documents/youtube-transcriber/whisper_transcribe.py`

Note: Whisper and yt-dlp are hard to unit test without real audio. We test the interface and error path only; correctness is verified manually.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_whisper.py
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_whisper.py -v
```

Expected: `ImportError: No module named 'whisper_transcribe'`

- [ ] **Step 3: Implement `whisper_transcribe.py`**

```python
# whisper_transcribe.py
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

    for attempt, delay in enumerate([0] + RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        proc = subprocess.run(
            ["yt-dlp", "-x", "--audio-format", "mp3", "-o", out_template, url],
            capture_output=True, text=True
        )
        if proc.returncode == 0:
            return _find_audio(tmp_dir, video_id)
        last_exc = proc.stderr.strip()
        if attempt == len(RETRY_DELAYS):
            break

    raise WhisperError(f"yt-dlp download failed after retries: {last_exc}")

def _find_audio(tmp_dir: str, video_id: str) -> str:
    matches = glob.glob(os.path.join(tmp_dir, f"{video_id}.*"))
    if not matches:
        raise WhisperError(f"No audio file found for {video_id} in {tmp_dir}")
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_whisper.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add whisper_transcribe.py tests/test_whisper.py
git commit -m "feat: Whisper transcription module with yt-dlp download"
```

---

## Task 7: Main CLI (`transcribe.py`)

**Files:**
- Create: `~/Documents/youtube-transcriber/transcribe.py`
- Create: `~/Documents/youtube-transcriber/tests/test_transcribe.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_transcribe.py
import json, pytest
from unittest.mock import patch, MagicMock
from transcribe import run_summaries_mode, build_result_json

def test_build_result_json():
    result = build_result_json(
        total=3, captions=1, whisper=1, skipped=1, live=0, failed=0,
        transcribed_ids=["a", "b"],
        failures=[]
    )
    data = json.loads(result)
    assert data["total"] == 3
    assert data["transcribed_ids"] == ["a", "b"]

def test_run_summaries_mode(tmp_path, capsys):
    import sqlite3
    from db import init_db, insert_video

    db_path = tmp_path / "transcripts.db"
    conn = init_db(str(db_path))
    insert_video(conn, {
        "video_id": "abc", "title": "Test", "url": "u",
        "playlist_id": None, "playlist_title": None, "language": "en",
        "method": "captions", "whisper_model": None,
        "summary": "A summary.", "transcript_path": "/tmp/abc.txt"
    })
    conn.close()

    run_summaries_mode(["abc", "missing"], str(db_path))
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) == 1
    assert data[0]["video_id"] == "abc"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_transcribe.py -v
```

Expected: `ImportError: No module named 'transcribe'`

- [ ] **Step 3: Implement `transcribe.py`**

```python
#!/Users/<username>/Documents/youtube-transcriber/.venv/bin/python
# transcribe.py
import argparse, json, os, sys, tempfile
from pathlib import Path

from db import init_db, video_exists, insert_video, get_summaries
from resolver import resolve, VideoInfo, PlaylistInfo
from captions import fetch_captions, NoTranscriptError
from whisper_transcribe import transcribe_audio, WhisperError
from summarize import extract_summary

TRANSCRIPTS_DIR = Path.home() / "transcripts"
DB_PATH = TRANSCRIPTS_DIR / "transcripts.db"

def main():
    parser = argparse.ArgumentParser(description="YouTube Transcriber")
    parser.add_argument("url", nargs="?", help="YouTube video or playlist URL")
    parser.add_argument("--model", default="medium", help="Whisper model (default: medium)")
    parser.add_argument("--force", action="store_true", help="Re-transcribe even if already in DB")
    parser.add_argument("--summaries", nargs="+", metavar="VIDEO_ID",
                        help="Query mode: print summaries for given video IDs")
    args = parser.parse_args()

    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = init_db(str(DB_PATH))

    if args.summaries:
        run_summaries_mode(args.summaries, str(DB_PATH))
        return

    if not args.url:
        parser.error("URL is required unless using --summaries")

    resolved = resolve(args.url)

    if isinstance(resolved, PlaylistInfo):
        videos = resolved.videos
        playlist_id = resolved.playlist_id
        playlist_title = resolved.playlist_title
    else:
        videos = [resolved]
        playlist_id = None
        playlist_title = None

    total = len(videos)
    counts = {"captions": 0, "whisper": 0, "skipped": 0, "live": 0, "failed": 0}
    transcribed_ids = []
    failures = []

    for i, video in enumerate(videos, 1):
        prefix = f"[{i}/{total}] {video.video_id} — \"{video.title}\""

        if video.is_live:
            print(f"{prefix} — skipped (live stream)", file=sys.stderr)
            counts["live"] += 1
            continue

        if not args.force and video_exists(conn, video.video_id):
            print(f"{prefix} — skipped (already transcribed)", file=sys.stderr)
            counts["skipped"] += 1
            continue

        transcript_path = TRANSCRIPTS_DIR / f"{video.video_id}.txt"
        text, lang, method, whisper_model = None, None, None, None

        # Try captions
        print(f"{prefix} — fetching captions...", end=" ", file=sys.stderr, flush=True)
        try:
            text, lang = fetch_captions(video.video_id)
            method = "captions"
            print("done", file=sys.stderr)
        except NoTranscriptError:
            print("no captions, downloading audio... transcribing...", end=" ", file=sys.stderr, flush=True)
            try:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    text, lang = transcribe_audio(video.video_id, args.model, tmp_dir)
                method = "whisper"
                whisper_model = args.model
                print("done", file=sys.stderr)
            except WhisperError as e:
                print(f"FAILED: {e}", file=sys.stderr)
                counts["failed"] += 1
                failures.append({"video_id": video.video_id, "reason": str(e)})
                continue

        # Write transcript
        tmp_path = transcript_path.with_suffix(".tmp")
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(transcript_path)

        # Store in DB
        summary = extract_summary(text)
        insert_video(conn, {
            "video_id": video.video_id,
            "title": video.title,
            "url": f"https://www.youtube.com/watch?v={video.video_id}",
            "playlist_id": playlist_id,
            "playlist_title": playlist_title,
            "language": lang,
            "method": method,
            "whisper_model": whisper_model,
            "summary": summary,
            "transcript_path": str(transcript_path),
        })
        counts[method] += 1
        transcribed_ids.append(video.video_id)

    print(
        f"Done. {total} videos encountered: "
        f"{counts['captions']} captions, {counts['whisper']} Whisper, "
        f"{counts['skipped']} skipped, {counts['failed']} failed.",
        file=sys.stderr
    )

    print(build_result_json(
        total=total,
        captions=counts["captions"],
        whisper=counts["whisper"],
        skipped=counts["skipped"],
        live=counts["live"],
        failed=counts["failed"],
        transcribed_ids=transcribed_ids,
        failures=failures
    ))

def run_summaries_mode(video_ids: list[str], db_path: str) -> None:
    conn = init_db(db_path)
    results = get_summaries(conn, video_ids)
    print(json.dumps(results))

def build_result_json(**kwargs) -> str:
    return json.dumps({
        "total": kwargs["total"],
        "captions": kwargs["captions"],
        "whisper": kwargs["whisper"],
        "skipped": kwargs["skipped"],
        "live": kwargs["live"],
        "failed": kwargs["failed"],
        "transcribed_ids": kwargs["transcribed_ids"],
        "failures": kwargs["failures"],
    }, indent=2)

if __name__ == "__main__":
    main()
```

**Important:** Replace `<username>` in the shebang with your actual macOS username.

- [ ] **Step 4: Make executable**

```bash
chmod +x ~/Documents/youtube-transcriber/transcribe.py
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
pytest tests/test_transcribe.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add transcribe.py tests/test_transcribe.py
git commit -m "feat: main CLI with full transcription orchestration"
```

---

## Task 8: Claude Skill

**Files:**
- Create: `~/.claude/skills/yt-transcriber/SKILL.md`

- [ ] **Step 1: Create skill directory**

```bash
mkdir -p ~/.claude/skills/yt-transcriber
```

- [ ] **Step 2: Write `SKILL.md`**

```markdown
---
name: yt-transcriber
description: >-
  Use this skill when the user wants to transcribe a YouTube video or playlist.
  Triggered by: "/yt-transcribe <url>", "transcribe this youtube video",
  "transcribe this playlist", or any message containing a YouTube URL
  (youtube.com or youtu.be) with intent to transcribe.
---

# YouTube Transcriber

Transcribe YouTube videos and playlists, then summarize and answer questions.

## How to Invoke

The user will provide a YouTube URL — either a single video or a playlist.

## Steps

1. **Run the transcription script** (stderr streams progress to the user):

```bash
python ~/Documents/youtube-transcriber/transcribe.py <url>
```

Capture stdout (JSON). Stream stderr to the user so they can see per-video progress.

2. **Parse the JSON result** from stdout:
   - `transcribed_ids`: list of video IDs successfully transcribed this run
   - `failures`: list of videos that failed (show these to the user)
   - `skipped`: count of already-transcribed videos

3. **Fetch summaries** for transcribed videos:

```bash
python ~/Documents/youtube-transcriber/transcribe.py --summaries <id1> <id2> ...
```

4. **Present results** to the user:
   - How many videos were transcribed, skipped, or failed
   - A brief summary of each video's content (from DB summaries)
   - Any failures with their reasons

5. **Prompt**: "What would you like to know about these videos?"

6. **Stay in context for Q&A**:
   - For overview questions ("what does this cover?", "compare these videos"): use the DB summaries — do NOT load full transcripts
   - For specific questions ("find where they discuss X", "what exactly did they say about Y"): load the `.txt` file from `~/transcripts/<video-id>.txt`
   - Before loading a full transcript, check its size. If it exceeds 120,000 characters, warn: "This transcript is very long and will use significant context. Continue?"
```

- [ ] **Step 3: Verify skill appears in Claude**

Restart Claude Code and confirm `yt-transcriber` appears in the skill list.

- [ ] **Step 4: Commit**

```bash
cd ~/.claude/skills/yt-transcriber
git init
git add SKILL.md
git commit -m "feat: yt-transcriber Claude skill"
```

---

## Task 9: End-to-End Smoke Test

- [ ] **Step 1: Run all unit tests**

```bash
cd ~/Documents/youtube-transcriber && source .venv/bin/activate
pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 2: Smoke test with a single short video**

Pick a short public YouTube video with known captions (e.g. a 1-2 min video).

```bash
python ~/Documents/youtube-transcriber/transcribe.py https://www.youtube.com/watch?v=<id>
```

Verify:
- Progress appears on stderr
- JSON result printed to stdout
- `~/transcripts/<id>.txt` exists and contains readable text
- `~/transcripts/transcripts.db` has a row for the video

- [ ] **Step 3: Smoke test --summaries**

```bash
python ~/Documents/youtube-transcriber/transcribe.py --summaries <id>
```

Expected: JSON array with `video_id`, `title`, `summary`

- [ ] **Step 4: Smoke test --force**

```bash
python ~/Documents/youtube-transcriber/transcribe.py --force https://www.youtube.com/watch?v=<id>
```

Expected: re-transcribes the video (not skipped)

- [ ] **Step 5: Smoke test via Claude skill**

In Claude Code, type: `transcribe this youtube video: https://www.youtube.com/watch?v=<id>`

Verify Claude invokes the script, shows progress, presents a summary, and answers a follow-up question.

- [ ] **Step 6: Final commit**

```bash
cd ~/Documents/youtube-transcriber
git add -A
git commit -m "chore: verified end-to-end smoke tests"
```
