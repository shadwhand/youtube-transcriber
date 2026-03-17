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
    assert data["captions"] == 1
    assert data["whisper"] == 1
    assert data["skipped"] == 1
    assert data["live"] == 0
    assert data["failed"] == 0
    assert data["transcribed_ids"] == ["a", "b"]
    assert data["failures"] == []

def test_run_summaries_mode(tmp_path, capsys):
    from db import init_db, insert_video

    db_path = tmp_path / "transcripts.db"
    conn = init_db(str(db_path))
    insert_video(conn, {
        "video_id": "abc", "title": "Test", "url": "u",
        "playlist_id": None, "playlist_title": None, "language": "en",
        "method": "captions", "whisper_model": None,
        "summary": "A summary.", "transcript_path": "/tmp/abc.txt"
    })

    run_summaries_mode(["abc", "missing"], conn)
    conn.close()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) == 1
    assert data[0]["video_id"] == "abc"
