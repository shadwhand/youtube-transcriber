from summarize import extract_summary

def test_extracts_three_sentences():
    text = "Hello world. This is a test. And a third. And a fourth."
    assert extract_summary(text) == "Hello world. This is a test. And a third."

def test_stops_at_500_chars():
    long_sentence = "A" * 300
    text = f"{long_sentence}. Short."
    result = extract_summary(text)
    assert len(result) <= 500

def test_handles_fewer_than_three_delimiters():
    text = "Only one sentence here"
    result = extract_summary(text)
    assert result == "Only one sentence here"

def test_handles_empty_string():
    assert extract_summary("") == ""

def test_exception_returns_none():
    assert extract_summary(None) is None

def test_joined_result_within_500_chars():
    # Two 249-char tokens + one 1-char token: without space accounting, naive sum is 499
    # but joined string would be 499+1+249+1+1 = 751 chars
    token1 = "A" * 249 + "."
    token2 = "B" * 249 + "."
    token3 = "C."
    text = f"{token1} {token2} {token3} More text."
    result = extract_summary(text)
    assert len(result) <= 500
