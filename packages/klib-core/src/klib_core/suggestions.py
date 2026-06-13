from __future__ import annotations

import re
import uuid
from collections import Counter
from typing import Any

from .models import Suggestion
from .retrieval import tokenize


def suggest_knowledge(texts: list[str], existing_terms: set[str]) -> list[Suggestion]:
    combined = "\n".join(texts)
    suggestions: list[Suggestion] = []
    term_counts = Counter(
        token
        for token in tokenize(combined)
        if len(token) >= 5 and token not in existing_terms
    )
    for term, count in term_counts.most_common(6):
        if count < 2:
            continue
        suggestions.append(
            _suggestion(
                "glossary",
                f"Define {term}",
                {"source_term": term, "target_term": term, "notes": "Review preferred wording."},
                f"Appears {count} times across package sources.",
                min(0.5 + count / 20, 0.9),
            )
        )

    modal_patterns = (
        ("must", "Preserve mandatory source requirements"),
        ("should", "Follow source recommendations unless package policy overrides them"),
        ("never", "Prevent explicitly prohibited behavior"),
    )
    lowered = combined.casefold()
    for marker, title in modal_patterns:
        if re.search(rf"\b{marker}\b", lowered):
            suggestions.append(
                _suggestion(
                    "rule",
                    title,
                    {
                        "title": title,
                        "body": f"Respect statements marked '{marker}' in trusted source evidence.",
                        "priority": 5,
                    },
                    f"Sources contain '{marker}' language.",
                    0.65,
                )
            )

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", combined)
        if 40 <= len(sentence.strip()) <= 260
    ]
    if sentences:
        sample = sentences[0]
        suggestions.append(
            _suggestion(
                "example",
                "Create a grounded example",
                {
                    "input": "Summarize one important package fact.",
                    "output": sample,
                    "task": "question_answering",
                    "mode": "default",
                },
                "A concise source sentence can seed a reviewed example.",
                0.55,
            )
        )
        key_terms = [term for term, _ in term_counts.most_common(2)]
        suggestions.append(
            _suggestion(
                "eval",
                "Add a source-grounding regression",
                {
                    "name": "Suggested source-grounding check",
                    "task": "question_answering",
                    "input": "State one important fact from the package sources and cite it.",
                    "checks": {
                        "must_include": key_terms,
                        "citation_required": True,
                    },
                },
                "Regression coverage is missing for prominent source terminology.",
                0.6,
            )
        )
    return suggestions[:12]


def _suggestion(
    kind: str,
    title: str,
    payload: dict[str, Any],
    reason: str,
    confidence: float,
) -> Suggestion:
    return Suggestion(
        id=uuid.uuid4().hex,
        kind=kind,  # type: ignore[arg-type]
        title=title,
        payload=payload,
        reason=reason,
        confidence=round(confidence, 2),
    )
