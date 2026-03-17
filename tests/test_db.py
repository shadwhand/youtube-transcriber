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
