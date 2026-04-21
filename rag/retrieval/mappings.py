from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from agent.datasets.bulk_writer import read_bulk_movies
from api.app.data.paths import ES_BULK_MOVIES_JSONL, ES_BULK_POISONED_MOVIES_JSONL
from rag.recsys.candidate_gen import CandidateDoc
from rag.retrieval.query_builder import dense_text_for_doc, hashed_dense_vector


def bulk_path_for_index(*, processed_dir: Path, index_name: str) -> tuple[Path, str]:
    if index_name == "movies":
        return (processed_dir / ES_BULK_MOVIES_JSONL).resolve(), "movies"
    if index_name == "movies_poisoned":
        return (processed_dir / ES_BULK_POISONED_MOVIES_JSONL).resolve(), "movies_poisoned"
    raise ValueError(f"Unsupported retrieval index: {index_name}")


def load_bulk_candidates(*, processed_dir: Path, index_name: str, seen_movie_ids: set[int]) -> list[CandidateDoc]:
    bulk_path, expected_index = bulk_path_for_index(processed_dir=processed_dir, index_name=index_name)
    docs = _read_bulk_docs_cached(str(bulk_path), expected_index, _mtime_ns(bulk_path))
    output: list[CandidateDoc] = []
    for doc in docs:
        movie_id = int(doc["movie_id"])
        if movie_id in seen_movie_ids:
            continue
        output.append(
            CandidateDoc(
                movie_id=movie_id,
                title=str(doc["title"]),
                genres=tuple(doc["genres"]),
                synopsis=str(doc["synopsis"]),
                bm25_score=0.0,
                poison_marker=bool(doc["poison_marker"]),
                poison_payload=str(doc["poison_payload"]),
            )
        )
    return output


def dense_corpus_rows(*, processed_dir: Path, index_name: str) -> list[dict[str, Any]]:
    bulk_path, expected_index = bulk_path_for_index(processed_dir=processed_dir, index_name=index_name)
    return _dense_rows_cached(str(bulk_path), expected_index, _mtime_ns(bulk_path))


@lru_cache(maxsize=8)
def _read_bulk_docs_cached(path_text: str, expected_index: str, mtime_ns: int) -> list[dict[str, Any]]:
    del mtime_ns
    raw_docs = read_bulk_movies(Path(path_text), expected_index=expected_index)
    output: list[dict[str, Any]] = []
    for doc in raw_docs:
        output.append(
            {
                "movie_id": int(str(doc.get("movie_id", "")).strip()),
                "title": str(doc.get("title", "") or "").strip(),
                "genres": [str(item).strip() for item in doc.get("genres", []) if str(item).strip()],
                "synopsis": str(doc.get("synopsis", "") or "").strip(),
                "poison_marker": bool(doc.get("poison_marker", False)),
                "poison_payload": str(doc.get("poison_payload", "") or "").strip(),
            }
        )
    return output


@lru_cache(maxsize=8)
def _dense_rows_cached(path_text: str, expected_index: str, mtime_ns: int) -> list[dict[str, Any]]:
    rows = _read_bulk_docs_cached(path_text, expected_index, mtime_ns)
    output: list[dict[str, Any]] = []
    for row in rows:
        output.append(
            {
                **row,
                "vector": hashed_dense_vector(
                    dense_text_for_doc(
                        title=str(row["title"]),
                        genres=[str(item) for item in row["genres"]],
                        synopsis=str(row["synopsis"]),
                    )
                ),
            }
        )
    return output


def _mtime_ns(path: Path) -> int:
    return path.stat().st_mtime_ns
