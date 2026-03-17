# YouTube Transcriber

Transcribe YouTube videos and playlists from the command line. Uses YouTube's built-in captions when available, falls back to local [Whisper](https://github.com/openai/whisper) transcription when they're not. Integrates with Claude Code as a skill for summarization and Q&A.

## Prerequisites

- Python 3.10+
- [Claude Code](https://claude.ai/code) (optional — for the Claude skill)

## Setup

```bash
git clone https://github.com/shadwhand/youtube-transcriber
cd youtube-transcriber
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Note:** `openai-whisper` installs PyTorch as a dependency. Expect a **1–3 GB download** on first install.

### Make the script executable

```bash
chmod +x transcribe.py
```

### Install the Claude skill (optional)

```bash
mkdir -p ~/.claude/skills/yt-transcriber
cp claude-skill/SKILL.md ~/.claude/skills/yt-transcriber/SKILL.md
```

Restart Claude Code — the skill will appear automatically.

## Usage

### Transcribe a single video

```bash
python transcribe.py "https://www.youtube.com/watch?v=<id>"
```

### Transcribe a playlist

```bash
python transcribe.py "https://www.youtube.com/playlist?list=<id>"
```

### Re-transcribe a video (overwrite existing)

```bash
python transcribe.py --force "https://www.youtube.com/watch?v=<id>"
```

### Use a different Whisper model

```bash
python transcribe.py --model large "https://www.youtube.com/watch?v=<id>"
```

Available models: `tiny`, `base`, `small`, `medium` (default), `large`

### Query summaries

```bash
python transcribe.py --summaries <video-id> [video-id ...]
```

## Output

- Transcripts saved to `~/transcripts/<video-id>.txt`
- Metadata and summaries stored in `~/transcripts/transcripts.db`
- Progress streamed to stderr, final JSON result to stdout

```
[1/3] dQw4w9WgXcQ — "Never Gonna Give You Up" — fetching captions... done
[2/3] abc123xyz — "Some Video" — no captions, downloading audio... transcribing... done
[3/3] def456uvw — skipped (already transcribed)
Done. 3 videos encountered: 1 captions, 1 Whisper, 1 skipped, 0 live, 0 failed.
```

## Using with Claude

Once the skill is installed, just paste a YouTube URL in Claude Code:

> `transcribe this playlist: https://www.youtube.com/playlist?list=...`

Claude will run the script, summarize each video, and stay available for Q&A. Full transcripts are only loaded into context when you ask specific questions.

## How it works

1. **Captions first** — fetches YouTube's built-in captions (fast, no download needed)
2. **Whisper fallback** — if no captions exist, downloads audio with `yt-dlp` and transcribes locally
3. **SQLite index** — stores metadata and a short summary per video so Claude can answer overview questions without loading full transcripts
4. **Deduplication** — skips videos already in the DB (use `--force` to re-transcribe)

## Dependencies

| Package | Purpose |
|---|---|
| `youtube-transcript-api` | Fetch YouTube captions |
| `yt-dlp` | Download audio when captions unavailable |
| `openai-whisper` | Local speech-to-text transcription |
| `pytest` | Testing |
