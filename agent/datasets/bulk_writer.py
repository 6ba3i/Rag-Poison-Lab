from __future__ import annotations

import json
from pathlib import Path


def read_bulk_movies(path: Path, expected_index: str = "movies") -> list[dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"Bulk JSONL file not found: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Bulk JSONL file is empty: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"Bulk JSONL file contains no lines: {path}")
    if len(lines) % 2 != 0:
        raise ValueError(f"Bulk JSONL must contain action/document line pairs: {path}")

    output: list[dict[str, object]] = []
    for line_idx in range(0, len(lines), 2):
        action_line = line_idx + 1
        doc_line = line_idx + 2

        try:
            action = json.loads(lines[line_idx])
            document = json.loads(lines[line_idx + 1])
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid JSON in bulk file at lines {action_line}-{doc_line}: {exc}") from exc

        if not isinstance(action, dict):
            raise ValueError(f"Action line must be a JSON object at line {action_line}")

        index_metadata = action.get("index")
        if not isinstance(index_metadata, dict):
            raise ValueError(f"Action line missing 'index' object at line {action_line}")

        action_index = str(index_metadata.get("_index", "")).strip()
        if action_index != expected_index:
            raise ValueError(
                f"Bulk action index mismatch at line {action_line}: "
                f"expected '{expected_index}', got '{action_index}'"
            )

        action_id = str(index_metadata.get("_id", "")).strip()
        if action_id == "":
            raise ValueError(f"Bulk action _id missing at line {action_line}")

        normalized = _normalize_doc(document=document, action_id=action_id, doc_line=doc_line)
        output.append(normalized)

    return output


def write_poisoned_bulk(path: Path, docs: list[dict[str, object]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered_docs = sorted(docs, key=lambda item: _movie_sort_key(str(item.get("movie_id", ""))))

    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for raw_doc in ordered_docs:
            doc = _normalize_doc(document=raw_doc, action_id=str(raw_doc.get("movie_id", "")).strip(), doc_line=0)
            action = {"index": {"_index": "movies_poisoned", "_id": doc["movie_id"]}}
            handle.write(json.dumps(action, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
            handle.write("\n")
            handle.write(json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
            handle.write("\n")
            count += 1

    return count


def _normalize_doc(*, document: object, action_id: str, doc_line: int) -> dict[str, object]:
    if not isinstance(document, dict):
        if doc_line > 0:
            raise ValueError(f"Document line must be a JSON object at line {doc_line}")
        raise ValueError("Document must be a JSON object")

    movie_id = str(document.get("movie_id", "")).strip()
    if movie_id == "":
        if doc_line > 0:
            raise ValueError(f"movie_id is required in bulk document line {doc_line}")
        raise ValueError("movie_id is required in document")

    if action_id and movie_id != action_id:
        if doc_line > 0:
            raise ValueError(f"movie_id does not match action _id at line {doc_line}")
        raise ValueError("movie_id does not match action _id")

    return {
        "movie_id": movie_id,
        "title": str(document.get("title", "") or "").strip(),
        "genres": _normalize_genres(document.get("genres", [])),
        "synopsis": str(document.get("synopsis", "") or "").strip(),
        "poison_marker": bool(document.get("poison_marker", False)),
        "poison_payload": str(document.get("poison_payload", "") or "").strip(),
    }


def _normalize_genres(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except Exception:  # noqa: BLE001
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [part.strip() for part in text.split("|") if part.strip()]
    return []


def _movie_sort_key(movie_id: str) -> tuple[int, int, str]:
    try:
        return (0, int(movie_id), "")
    except Exception:  # noqa: BLE001
        return (1, 0, movie_id)
