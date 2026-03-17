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
