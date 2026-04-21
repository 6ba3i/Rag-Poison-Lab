from __future__ import annotations

from hashlib import sha1
import math
import re

import numpy as np

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
DENSE_VECTOR_DIMENSIONS = 256


def dense_text_for_doc(*, title: str, genres: list[str], synopsis: str) -> str:
    genre_text = " ".join(item.strip() for item in genres if item.strip())
    return " ".join(part for part in [title.strip(), genre_text, synopsis.strip()] if part).strip()


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def hashed_dense_vector(text: str, *, dimensions: int = DENSE_VECTOR_DIMENSIONS) -> np.ndarray:
    vector = np.zeros(dimensions, dtype=float)
    for token in tokenize(text):
        digest = sha1(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1.0

    norm = math.sqrt(float(np.dot(vector, vector)))
    if norm > 0.0:
        vector = vector / norm
    return vector


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        return 0.0
    return float(np.dot(left, right))
