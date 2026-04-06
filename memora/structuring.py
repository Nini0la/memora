from __future__ import annotations

import re
from collections import Counter

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
_STOP_WORDS = {
    "about",
    "across",
    "after",
    "also",
    "and",
    "are",
    "because",
    "been",
    "being",
    "but",
    "can",
    "for",
    "from",
    "has",
    "have",
    "into",
    "its",
    "more",
    "not",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "those",
    "through",
    "use",
    "with",
}


def generate_outline(title: str | None, raw_text: str) -> dict:
    cleaned = raw_text.strip()
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(cleaned) if s.strip()]
    if not sentences:
        sentences = [cleaned]

    topic_title = title.strip() if title and title.strip() else _title_from_text(sentences[0])

    chunk_count = min(3, max(1, len(sentences)))
    chunk_size = (len(sentences) + chunk_count - 1) // chunk_count
    chunks = [
        sentences[index : index + chunk_size]
        for index in range(0, len(sentences), chunk_size)
        if sentences[index : index + chunk_size]
    ]

    subtopics = []
    for index, chunk in enumerate(chunks, start=1):
        joined = " ".join(chunk).strip()
        key_concepts = _extract_key_concepts(joined)
        subtopic_title = _title_from_text(chunk[0])
        summary = joined[:260]
        prompts = [
            f"Explain {key_concepts[0]} in this subtopic.",
            "What are the most important ideas from this section?",
        ]
        subtopics.append(
            {
                "title": f"{index}. {subtopic_title}",
                "key_concepts": key_concepts,
                "summary": summary,
                "recall_prompts": prompts,
            }
        )

    return {"topic_title": topic_title, "subtopics": subtopics}


def _title_from_text(sentence: str) -> str:
    words = _WORD_RE.findall(sentence)
    if not words:
        return "Untitled Topic"
    return " ".join(words[:6]).strip().title()


def _extract_key_concepts(text: str) -> list[str]:
    words = [w.lower() for w in _WORD_RE.findall(text)]
    filtered = [w for w in words if len(w) > 3 and w not in _STOP_WORDS]
    counts = Counter(filtered)
    concepts = [word for word, _ in counts.most_common(4)]
    if not concepts:
        fallback = [w.lower() for w in _WORD_RE.findall(text)[:2]]
        concepts = fallback or ["concept"]
    return concepts
