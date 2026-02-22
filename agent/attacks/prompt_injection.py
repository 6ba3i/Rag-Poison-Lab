from __future__ import annotations

from agent.attacks.base import DEFAULT_INJECTION_PAYLOAD, clone_docs, select_poison_indices


def apply_prompt_injection(
    docs: list[dict[str, object]],
    *,
    poison_fraction: float,
    payload_text: str,
) -> list[dict[str, object]]:
    output = clone_docs(docs)
    selected = select_poison_indices(output, poison_fraction)
    payload = payload_text.strip() or DEFAULT_INJECTION_PAYLOAD

    for idx in selected:
        doc = output[idx]
        doc["poison_marker"] = True
        doc["poison_payload"] = payload

    return output
