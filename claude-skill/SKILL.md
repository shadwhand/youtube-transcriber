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
