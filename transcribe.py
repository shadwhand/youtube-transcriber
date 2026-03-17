#!/Users/jshin/Documents/youtube-transcriber/.venv/bin/python
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
    try:
        if args.summaries:
            run_summaries_mode(args.summaries, conn)
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

            # Write transcript (atomic via .tmp)
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
            f"{counts['skipped']} skipped, {counts['live']} live, {counts['failed']} failed.",
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
    finally:
        conn.close()

def run_summaries_mode(video_ids: list[str], conn) -> None:
    results = get_summaries(conn, video_ids)
    print(json.dumps(results))

def build_result_json(
    total: int, captions: int, whisper: int, skipped: int,
    live: int, failed: int, transcribed_ids: list, failures: list
) -> str:
    return json.dumps({
        "total": total,
        "captions": captions,
        "whisper": whisper,
        "skipped": skipped,
        "live": live,
        "failed": failed,
        "transcribed_ids": transcribed_ids,
        "failures": failures,
    }, indent=2)

if __name__ == "__main__":
    main()
