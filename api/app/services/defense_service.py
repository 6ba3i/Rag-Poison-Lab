from __future__ import annotations

from dataclasses import dataclass
import re

from common.schemas.defense_config import DefenseConfig
from rag.recsys.candidate_gen import CandidateDoc

WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class DefenseApplicationResult:
    candidates: list[CandidateDoc]
    debug: dict[str, object]


def apply_retrieval_defense(
    *,
    candidates: list[CandidateDoc],
    config: DefenseConfig | None,
) -> DefenseApplicationResult:
    if config is None or not config.enabled or not config.retrieval_guard_enabled:
        return DefenseApplicationResult(
            candidates=list(candidates),
            debug={"enabled": False, "suspicious_movie_ids": [], "filtered_movie_ids": [], "penalized_movie_ids": []},
        )

    suspicious_ids: list[int] = []
    filtered_ids: list[int] = []
    penalized_ids: list[int] = []
    output: list[CandidateDoc] = []

    for candidate in candidates:
        suspicious = candidate_is_suspicious(candidate=candidate, config=config)
        if suspicious:
            suspicious_ids.append(candidate.movie_id)

        if suspicious and config.retrieval_suspicion_mode == "filter":
            filtered_ids.append(candidate.movie_id)
            continue

        if suspicious and config.retrieval_suspicion_mode == "penalize":
            penalized_ids.append(candidate.movie_id)
            output.append(
                CandidateDoc(
                    movie_id=candidate.movie_id,
                    title=candidate.title,
                    genres=candidate.genres,
                    synopsis=candidate.synopsis,
                    bm25_score=round(float(candidate.bm25_score) * float(config.retrieval_penalty_weight), 6),
                    poison_marker=candidate.poison_marker,
                    poison_payload=candidate.poison_payload,
                )
            )
            continue

        output.append(candidate)

    return DefenseApplicationResult(
        candidates=output,
        debug={
            "enabled": True,
            "retrieval_suspicion_mode": config.retrieval_suspicion_mode,
            "suspicious_movie_ids": suspicious_ids,
            "filtered_movie_ids": filtered_ids,
            "penalized_movie_ids": penalized_ids,
        },
    )


def sanitize_candidates_for_prompt(
    *,
    candidates: list[CandidateDoc],
    config: DefenseConfig | None,
) -> tuple[list[CandidateDoc], dict[str, object]]:
    if config is None or not config.enabled or not config.rerank_sanitization_enabled:
        return list(candidates), {"enabled": False, "sanitized_movie_ids": []}

    sanitized_ids: list[int] = []
    output: list[CandidateDoc] = []
    for candidate in candidates:
        sanitized_title = sanitize_text(candidate.title, config=config)
        sanitized_synopsis = sanitize_text(candidate.synopsis, config=config)
        sanitized_payload = ""
        changed = (
            sanitized_title != candidate.title
            or sanitized_synopsis != candidate.synopsis
            or candidate.poison_payload.strip() != ""
        )
        if changed:
            sanitized_ids.append(candidate.movie_id)
        output.append(
            CandidateDoc(
                movie_id=candidate.movie_id,
                title=sanitized_title,
                genres=candidate.genres,
                synopsis=sanitized_synopsis,
                bm25_score=candidate.bm25_score,
                poison_marker=candidate.poison_marker,
                poison_payload=sanitized_payload,
            )
        )
    return output, {"enabled": True, "sanitized_movie_ids": sanitized_ids}


def candidate_is_suspicious(*, candidate: CandidateDoc, config: DefenseConfig) -> bool:
    if candidate.poison_marker:
        return True
    if candidate.poison_payload.strip():
        return True
    combined = " ".join(
        [
            candidate.title,
            " ".join(candidate.genres),
            candidate.synopsis,
            candidate.poison_payload,
        ]
    ).lower()
    return any(pattern in combined for pattern in config.suspicious_patterns)


def sanitize_text(text: str, *, config: DefenseConfig) -> str:
    output = text
    for pattern in config.suspicious_patterns:
        output = re.sub(re.escape(pattern), "[redacted]", output, flags=re.IGNORECASE)
    return WHITESPACE_PATTERN.sub(" ", output).strip()
