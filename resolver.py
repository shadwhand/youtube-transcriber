# resolver.py
import subprocess, json
from dataclasses import dataclass, field
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
    videos: list["VideoInfo"] = field(default_factory=list)

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
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"yt-dlp timed out after 120s: {' '.join(cmd)}") from e
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {proc.stderr.strip()}")
    return proc.stdout
