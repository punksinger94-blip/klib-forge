from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class RetrievalPolicy(BaseModel):
    top_k: int = Field(default=8, ge=1, le=50)
    use_hybrid_search: bool = False
    require_citations: bool = True


class ModelPolicy(BaseModel):
    default_provider: str = "ollama"
    default_model: str = "gemma3"
    allow_online_models: bool = False


class Manifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    version: str = Field(default="0.1.0", pattern=r"^\d+\.\d+\.\d+(?:[-+].+)?$")
    description: str = ""
    domain: str = "general"
    languages: list[str] = Field(default_factory=lambda: ["en"])
    license: str = "CC-BY-4.0"
    klib_format_version: Literal["0.1"] = "0.1"
    default_mode: str = "default"
    supported_tasks: list[str] = Field(default_factory=lambda: ["question_answering"])
    retrieval_policy: RetrievalPolicy = Field(default_factory=RetrievalPolicy)
    model_policy: ModelPolicy = Field(default_factory=ModelPolicy)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class SearchResult(BaseModel):
    chunk_id: str
    source_id: str
    source_title: str
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class AskResult(BaseModel):
    output: str
    provider: str
    model: str
    retrieved_context: list[SearchResult]
    prompt_preview: str
    latency_ms: int
    citations: list[str] = Field(default_factory=list)


class EvalCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class EvalResult(BaseModel):
    eval_id: str
    score: float
    output: str
    checks: list[EvalCheck]


class CompileResult(BaseModel):
    library_id: str
    sources: int
    chunks: int
    keywords: list[str]
    snapshot_id: str


class DiffResult(BaseModel):
    from_snapshot: str | None
    to_snapshot: str
    added_sources: list[str] = Field(default_factory=list)
    removed_sources: list[str] = Field(default_factory=list)
    added_glossary: list[str] = Field(default_factory=list)
    removed_glossary: list[str] = Field(default_factory=list)
    changed_glossary: list[str] = Field(default_factory=list)
    added_rules: list[str] = Field(default_factory=list)
    removed_rules: list[str] = Field(default_factory=list)
    added_evals: list[str] = Field(default_factory=list)
    removed_evals: list[str] = Field(default_factory=list)

