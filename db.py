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
        tuple(video_ids)
    ).fetchall()
    return [dict(r) for r in rows]
