import re

def extract_summary(text: str | None) -> str | None:
    try:
        if not text:
            return text if text == "" else None
        # Lookbehind keeps the punctuation attached to the preceding token
        tokens = re.split(r'(?<=[.?!])\s', text)
        collected = []
        char_count = 0
        for token in tokens:
            if len(collected) >= 3 or char_count >= 500:
                break
            collected.append(token)
            char_count += len(token)
        return " ".join(collected)
    except Exception:
        return None
