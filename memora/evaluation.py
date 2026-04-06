from __future__ import annotations

import re

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]*")


def evaluate_answer(answer_text: str, key_concepts: list[str]) -> dict:
    answer_tokens = {w.lower() for w in _WORD_RE.findall(answer_text)}
    concept_tokens = [concept.lower() for concept in key_concepts if concept]

    matched = [concept for concept in concept_tokens if concept in answer_tokens]
    missing = [concept for concept in concept_tokens if concept not in answer_tokens]

    completeness = len(matched) / len(concept_tokens) if concept_tokens else 0.0
    length_factor = min(len(answer_tokens) / 35, 1.0)

    score = int((completeness * 70) + (length_factor * 30))
    level = _score_to_level(score)

    if missing:
        feedback = (
            "You captured part of the concept but missed key ideas: "
            + ", ".join(missing[:4])
            + "."
        )
    else:
        feedback = "Strong recall coverage. Keep practicing for fluency and structure."

    return {
        "score": score,
        "level": level,
        "missing_concepts": missing,
        "feedback": feedback,
    }


def _score_to_level(score: int) -> int:
    if score < 20:
        return 0
    if score < 40:
        return 1
    if score < 55:
        return 2
    if score < 70:
        return 3
    if score < 85:
        return 4
    return 5
