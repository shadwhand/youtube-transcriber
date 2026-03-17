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
