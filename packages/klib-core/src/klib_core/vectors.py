from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import httpx

from .errors import KlibError
from .models import SearchResult
from .retrieval import tokenize

VECTOR_SIZE = 256


def embed_text(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    tokens = tokenize(text)
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "little")
        index = value % VECTOR_SIZE
        sign = -1.0 if value & 1 else 1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 8) for value in vector]


class LocalVectorIndex:
    def __init__(self, path: Path):
        self.path = path

    def build(self, chunks: list[dict[str, Any]]) -> None:
        payload = {
            "version": "1",
            "size": VECTOR_SIZE,
            "records": [
                {**chunk, "vector": embed_text(chunk["text"])}
                for chunk in chunks
            ],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        if not self.path.exists():
            return []
        query_vector = embed_text(query)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        results = []
        for record in payload.get("records", []):
            score = sum(
                left * right for left, right in zip(query_vector, record["vector"], strict=False)
            )
            if score > 0:
                results.append(_result(record, score))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]


class ChromaVectorIndex:
    def __init__(self, path: Path, collection: str):
        self.path = path
        self.collection = collection

    def _client(self) -> Any:
        try:
            import chromadb
        except ImportError as exc:
            raise KlibError(
                "Chroma adapter requires `pip install klib-forge[chroma]`"
            ) from exc
        return chromadb.PersistentClient(path=str(self.path))

    def build(self, chunks: list[dict[str, Any]]) -> None:
        client = self._client()
        try:
            client.delete_collection(self.collection)
        except Exception:
            pass
        collection = client.get_or_create_collection(self.collection)
        if chunks:
            collection.add(
                ids=[chunk["id"] for chunk in chunks],
                embeddings=[embed_text(chunk["text"]) for chunk in chunks],
                documents=[chunk["text"] for chunk in chunks],
                metadatas=[
                    {
                        "source_id": chunk["source_id"],
                        "source_title": chunk["source_title"],
                        "metadata_json": json.dumps(chunk.get("metadata", {})),
                    }
                    for chunk in chunks
                ],
            )

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        collection = self._client().get_collection(self.collection)
        response = collection.query(
            query_embeddings=[embed_text(query)],
            n_results=top_k,
        )
        results = []
        for index, chunk_id in enumerate(response["ids"][0]):
            metadata = response["metadatas"][0][index]
            distance = response["distances"][0][index]
            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    source_id=metadata["source_id"],
                    source_title=metadata["source_title"],
                    text=response["documents"][0][index],
                    score=round(1 / (1 + distance), 6),
                    metadata=json.loads(metadata.get("metadata_json", "{}")),
                )
            )
        return results


class QdrantVectorIndex:
    def __init__(self, url: str, collection: str):
        self.url = url.rstrip("/")
        self.collection = collection

    def build(self, chunks: list[dict[str, Any]]) -> None:
        response = httpx.put(
            f"{self.url}/collections/{self.collection}",
            json={"vectors": {"size": VECTOR_SIZE, "distance": "Cosine"}},
            timeout=30,
        )
        response.raise_for_status()
        points = [
            {
                "id": _point_id(chunk["id"]),
                "vector": embed_text(chunk["text"]),
                "payload": {
                    "chunk_id": chunk["id"],
                    "source_id": chunk["source_id"],
                    "source_title": chunk["source_title"],
                    "text": chunk["text"],
                    "metadata": chunk.get("metadata", {}),
                },
            }
            for chunk in chunks
        ]
        for start in range(0, len(points), 100):
            response = httpx.put(
                f"{self.url}/collections/{self.collection}/points",
                json={"points": points[start : start + 100]},
                timeout=60,
            )
            response.raise_for_status()

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        response = httpx.post(
            f"{self.url}/collections/{self.collection}/points/search",
            json={"vector": embed_text(query), "limit": top_k, "with_payload": True},
            timeout=30,
        )
        response.raise_for_status()
        return [
            SearchResult(
                chunk_id=item["payload"]["chunk_id"],
                source_id=item["payload"]["source_id"],
                source_title=item["payload"]["source_title"],
                text=item["payload"]["text"],
                score=round(float(item["score"]), 6),
                metadata=item["payload"].get("metadata", {}),
            )
            for item in response.json()["result"]
        ]


def _result(record: dict[str, Any], score: float) -> SearchResult:
    return SearchResult(
        chunk_id=record["id"],
        source_id=record["source_id"],
        source_title=record["source_title"],
        text=record["text"],
        score=round(score, 6),
        metadata=record.get("metadata", {}),
    )


def _point_id(value: str) -> int:
    return int.from_bytes(hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest(), "little")
