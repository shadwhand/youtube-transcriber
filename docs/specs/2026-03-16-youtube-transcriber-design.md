# YouTube Transcriber — Design Spec

**Date:** 2026-03-16
**Status:** Approved

---

## Overview

A two-part system that transcribes YouTube videos and playlists, stores results locally, and exposes them to Claude for summarization and Q&A.

1. **`~/Documents/youtube-transcriber/transcribe.py`** — Python CLI script that handles fetching, transcribing, and storing
2. **`~/.claude/skills/yt-transcriber/SKILL.md`** — Claude skill that invokes the script and reasons over results

---

## Architecture

### Script (`~/Documents/youtube-transcriber/transcribe.py`)

Accepts a single YouTube video URL or playlist URL. For each video:

1. Auto-create `~/transcripts/` directory and `~/transcripts/transcripts.db` if they don't exist
2. Check SQLite DB for existing video ID — skip if already transcribed (unless `--force`)
3. Detect if URL is a live stream or active premiere via metadata — skip with message "skipped (live stream)"
4. Attempt to fetch captions via `youtube-transcript-api` with retry/backoff (see below)
5. If no captions available: download audio with `yt-dlp` (same retry/backoff policy), transcribe with local Whisper (`medium` model), delete temp audio file
6. Save transcript as `~/transcripts/<video-id>.txt` (plain text, timestamps stripped, segments joined with a single space)
7. Store metadata and extractive summary in DB (see summary rules below)
8. Print per-video progress to **stderr** throughout

**URL classification:**
- If the URL contains a `list=` query parameter, treat it as a playlist URL and populate `playlist_id` and `playlist_title`
- If the URL is a combined video+playlist URL (e.g. `watch?v=ID&list=PL...`), treat it as a playlist: use `yt-dlp` to extract the full playlist (no API key required), process all videos in the playlist's own order (ignoring the `v=` parameter for ordering purposes). The `v=ID` video is processed as part of the playlist if it appears in it; if it does not appear in the playlist, it is silently ignored.
- Otherwise, treat as a single video; `playlist_id` and `playlist_title` are NULL

**Progress output (stderr):**
```
[1/5] dQw4w9WgXcQ — "Never Gonna Give You Up" — fetching captions... done
[2/5] abc123xyz — "Some Other Video" — no captions, downloading audio... transcribing... done
[3/5] def456uvw — skipped (already transcribed)
[4/5] ghi789rst — FAILED: HTTP 403 (private video)
[5/5] jkl012uvw — fetching captions... done
Done. 5 videos encountered: 2 captions, 1 Whisper, 1 skipped, 1 failed.
```

**Completion output (JSON to stdout — the only output on stdout):**
```json
{
  "total": 5,
  "captions": 2,
  "whisper": 1,
  "skipped": 1,
  "live": 0,
  "failed": 1,
  "transcribed_ids": ["dQw4w9WgXcQ", "abc123xyz", "jkl012uvw"],
  "failures": [
    {"video_id": "ghi789rst", "reason": "HTTP 403 (private video)"}
  ]
}
```

- `total` = all videos encountered (captions + whisper + skipped + live + failed)
- `skipped` = videos already in DB (not re-processed)
- `live` = videos skipped because they are active live streams or premieres
- `transcribed_ids` = list of video IDs that were successfully transcribed this run (captions or whisper, including force re-transcriptions). The skill uses this list to look up summaries in the DB.

**Retry/backoff policy (applies to both caption fetching and yt-dlp audio download):**
- Max 3 retries
- Initial delay: 2s
- Multiplier: 2x (delays: 2s, 4s, 8s)
- No jitter
- After 3 failed retries on caption fetch: fall back to Whisper
- After 3 failed retries on audio download: skip video, add to `failures`

**Error handling:**
- HTTP 429 (rate limit): retry with backoff
- HTTP 403/404 (private, unavailable, deleted): skip immediately (no retry), log to stderr, add to `failures`
- Connection timeout / DNS failure: retry with backoff; after 3 retries, skip and add to `failures`
- HTTP 5xx: retry with backoff; after 3 retries, skip and add to `failures`
- Live streams / active premieres: skip immediately, log "skipped (live stream)" to stderr
- Whisper failure: skip video, log to stderr, add to `failures`

**`--force` behavior:**
- Re-transcribe the video even if it exists in DB
- Write the new `.txt` file only after transcription succeeds — if transcription fails, the original `.txt` and DB row are preserved unchanged
- On success: overwrite `.txt` file, update DB using `INSERT OR REPLACE INTO` (which deletes and re-inserts the row). All fields are populated from the current run's context — if `--force` is run with a single-video URL, `playlist_id` and `playlist_title` are NULL regardless of how the video was originally transcribed. Playlist association from previous runs is not preserved.

**Caption track selection (when multiple tracks exist):**
Priority order:
1. Manual English captions (`en`, `is_generated=False`)
2. Auto-generated English captions (`en`, `is_generated=True`)
3. First available manual caption in any language
4. First available auto-generated caption in any language

**Transcript file format:**
- Timestamps stripped from both caption segments and Whisper output
- All segments joined with a single space into one block of text
- No formatting, headers, or metadata in the `.txt` file

**Extractive summary rules:**
- Use a lookbehind regex split on `(?<=[.?!])\s` — false splits on abbreviations (e.g. `Dr. `, `U.S. `) are acceptable, but punctuation is preserved on the preceding token
- Collect tokens until either 3 tokens have been collected OR the running character count reaches 500 — whichever comes first
- If the transcript has fewer than 3 sentence-ending delimiters, include any remaining trailing text as the final token (even if unterminated)
- Join collected tokens with a space to form the summary string
- If summary generation raises an exception, store NULL (non-fatal — script continues)

**Flags:**
- `--model <name>` — override Whisper model (default: `medium`)
- `--force` — re-transcribe even if video ID exists in DB
- `--summaries <video_id> [video_id ...]` — query mode: print a JSON array of `{video_id, title, summary}` objects for the given IDs, then exit immediately without transcribing anything. IDs not found in the DB are silently omitted from the array. Used by the skill to read summaries without raw SQL.

---

### SQLite Database (`~/transcripts/transcripts.db`)

One row per video. Created automatically on first run.

| Column | Type | Description |
|---|---|---|
| `video_id` | TEXT PK | YouTube video ID |
| `title` | TEXT | Video title |
| `url` | TEXT | Full YouTube URL |
| `playlist_id` | TEXT | Playlist ID if applicable, NULL for single videos |
| `playlist_title` | TEXT | Playlist title if applicable |
| `language` | TEXT | ISO 639-1 code. For captions: language of selected track. For Whisper: language detected by Whisper. NULL if unknown. |
| `method` | TEXT | `captions` or `whisper` |
| `whisper_model` | TEXT | Whisper model used (e.g. `medium`), NULL if captions |
| `summary` | TEXT | Extractive summary (see rules above). NULL if generation fails. |
| `transcribed_at` | TEXT | ISO 8601 timestamp (UTC) |
| `transcript_path` | TEXT | Absolute path to `.txt` file |

---

### Transcript Files (`~/transcripts/`)

- One `.txt` file per video: `~/transcripts/<video-id>.txt`
- Plain text, no compression, no timestamps, no metadata
- Flat directory — no subdirectories
- Directory auto-created on first run

---

## Claude Skill (`~/.claude/skills/yt-transcriber/SKILL.md`)

**Trigger phrases:**
- `/yt-transcribe <url>`
- "transcribe this youtube video: <url>"
- "transcribe this playlist: <url>"
- Any message containing a YouTube URL with intent to transcribe

**Behavior after invocation:**
1. Run `python ~/Documents/youtube-transcriber/transcribe.py <url>`, surface stderr progress to user in real time
2. Parse JSON from stdout on completion
3. Run `python ~/Documents/youtube-transcriber/transcribe.py --summaries <id1> <id2> ...` using `transcribed_ids` from the JSON to fetch summaries
4. Present a structured response: count of videos transcribed, key topics per video (from DB summaries)
5. Prompt: "What would you like to know about these videos?"
6. Stay in context for Q&A — load full `.txt` transcripts on demand (see context rules below)

**Context management — when to load full transcripts:**
- Use DB summaries for: overview questions, topic questions, "what does this playlist cover", comparisons between videos
- Load full `.txt` for: requests for specific quotes, details, or examples; "find where they talk about X"; questions that require precise content
- Before loading, check file size. If the `.txt` file exceeds 120,000 characters (~30k tokens at 4 chars/token), warn the user: "This transcript is very long — loading it will use significant context. Continue?"

---

## Dependencies

**One-time setup:**

```bash
cd ~/youtube-transcriber
python -m venv .venv
source .venv/bin/activate
pip install yt-dlp youtube-transcript-api openai-whisper
```

**Note:** `openai-whisper` installs PyTorch — a machine learning framework required for local audio transcription. Expect a **1–3 GB download** on first install.

The script's shebang should use the venv Python. Replace `<username>` with your actual macOS username:
```python
#!/Users/<username>/youtube-transcriber/.venv/bin/python
```

---

## File Layout

```
~/
├── youtube-transcriber/
│   ├── transcribe.py          # CLI script
│   └── .venv/                 # Python virtual environment
└── transcripts/
    ├── transcripts.db          # SQLite database (metadata + summaries)
    ├── dQw4w9WgXcQ.txt        # Transcript files (video ID as filename)
    ├── abc123xyz.txt
    └── ...

~/.claude/skills/
└── yt-transcriber/
    └── SKILL.md               # Claude skill definition
```

---

## Out of Scope

- Translation of non-English transcripts
- Per-video Whisper model selection
- Web UI
- Automatic re-transcription when videos are updated
- Authentication for age-restricted content
