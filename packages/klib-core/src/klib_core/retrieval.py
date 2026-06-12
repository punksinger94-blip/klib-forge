from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .models import SearchResult

TOKEN_PATTERN = re.compile(r"[\w'-]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_PATTERN.findall(text) if len(token) > 1]


class LocalIndex:
    """Small deterministic TF-IDF index used by the offline v0.1 runtime."""

    def __init__(self, path: Path):
        self.path = path

    def build(self, chunks: list[dict[str, Any]]) -> None:
        document_frequency: Counter[str] = Counter()
        records = []
        for chunk in chunks:
            counts = Counter(tokenize(chunk["text"]))
            document_frequency.update(counts.keys())
            records.append({**chunk, "terms": dict(counts)})
        payload = {
            "version": "0.1",
            "document_count": len(records),
            "document_frequency": dict(document_frequency),
            "records": records,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def search(self, query: str, top_k: int = 8) -> list[SearchResult]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        query_terms = Counter(tokenize(query))
        total_documents = max(int(payload.get("document_count", 0)), 1)
        document_frequency = payload.get("document_frequency", {})
        query_weights: dict[str, float] = {}
        for term, frequency in query_terms.items():
            inverse = math.log((total_documents + 1) / (document_frequency.get(term, 0) + 1)) + 1
            query_weights[term] = (1 + math.log(frequency)) * inverse

        results: list[SearchResult] = []
        for record in payload.get("records", []):
            term_counts = record.get("terms", {})
            score = 0.0
            matched = 0
            for term, query_weight in query_weights.items():
                count = term_counts.get(term, 0)
                if count:
                    inverse = math.log(
                        (total_documents + 1) / (document_frequency.get(term, 0) + 1)
                    ) + 1
                    score += query_weight * (1 + math.log(count)) * inverse
                    matched += 1
            if score:
                score *= 1 + (matched / max(len(query_weights), 1))
                results.append(
                    SearchResult(
                        chunk_id=record["id"],
                        source_id=record["source_id"],
                        source_title=record["source_title"],
                        text=record["text"],
                        score=round(score, 6),
                        metadata=record.get("metadata", {}),
                    )
                )
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]


def top_keywords(chunks: list[dict[str, Any]], limit: int = 20) -> list[str]:
    frequencies: defaultdict[str, int] = defaultdict(int)
    stop = {
        "about", "after", "also", "and", "are", "been", "but", "can", "for", "from",
        "have", "into", "its", "not", "that", "the", "their", "then", "this", "use",
        "using", "was", "were", "will", "with", "you", "your",
    }
    for chunk in chunks:
        for term in tokenize(chunk["text"]):
            if len(term) > 2 and term not in stop:
                frequencies[term] += 1
    ranked = sorted(frequencies.items(), key=lambda item: (-item[1], item[0]))
    return [term for term, _ in ranked[:limit]]
