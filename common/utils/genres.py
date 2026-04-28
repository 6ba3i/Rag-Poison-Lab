from __future__ import annotations


def normalize_genres(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return []
        return [part.strip() for part in text.split("|") if part.strip()]
    return []
