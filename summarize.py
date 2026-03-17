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
            if len(collected) >= 3:
                break
            prospective = char_count + len(token) + (1 if collected else 0)
            if prospective > 500:
                break
            char_count = prospective
            collected.append(token)
        return " ".join(collected)
    except Exception:
        return None
