from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag.recsys.candidate_gen import CandidateDoc


@dataclass(frozen=True)
class RetrievalResult:
    candidates: list[CandidateDoc]
    debug: dict[str, Any]
