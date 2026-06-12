from __future__ import annotations

import json
import re
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from .errors import KlibError
from .files import chunk_text, clean_text, extract_text
from .library import LibraryManager
from .models import (
    AskResult,
    CompileResult,
    DiffResult,
    EvalCheck,
    EvalResult,
    SearchResult,
    utc_now,
)
from .prompt import build_prompt
from .providers import get_provider
from .retrieval import LocalIndex, top_keywords


class ForgeEngine:
    def __init__(self, manager: LibraryManager | None = None):
        self.manager = manager or LibraryManager()

    def compile(self, identifier: str | Path) -> CompileResult:
        manifest, library_path = self.manager.get(identifier)
        sources = self.manager.sources(identifier)
        chunks: list[dict[str, Any]] = []
        chunks_path = library_path / "chunks" / "chunks.jsonl"
        self.manager.db.execute("DELETE FROM chunks WHERE library_id = ?", (manifest.id,))

        for source in sources:
            source_path = library_path / source["path"]
            cleaned = clean_text(extract_text(source_path))
            source_chunks = chunk_text(cleaned)
            for index, text in enumerate(source_chunks):
                chunk_id = f"{source['id']}:{index}"
                item = {
                    "id": chunk_id,
                    "source_id": source["id"],
                    "source_title": source["title"],
                    "text": text,
                    "metadata": {
                        "chunk_index": index,
                        "source_type": source["type"],
                        "trust_level": source["trust_level"],
                    },
                }
                chunks.append(item)
                self.manager.db.execute(
                    """
                    INSERT INTO chunks
                        (id, library_id, source_id, text, chunk_index, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        manifest.id,
                        source["id"],
                        text,
                        index,
                        self.manager.db.json(item["metadata"]),
                        utc_now(),
                    ),
                )

        chunks_path.parent.mkdir(parents=True, exist_ok=True)
        chunks_path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in chunks),
            encoding="utf-8",
        )
        LocalIndex(library_path / "indexes" / "local-index.json").build(chunks)
        keywords = top_keywords(chunks)
        build_metadata = {
            "library_id": manifest.id,
            "version": manifest.version,
            "compiled_at": utc_now(),
            "source_count": len(sources),
            "chunk_count": len(chunks),
            "keywords": keywords,
            "retrieval_engine": "local-tfidf",
        }
        (library_path / "build" / "metadata.json").write_text(
            json.dumps(build_metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        snapshot_id = self._snapshot(identifier)
        self.manager._touch(identifier)
        return CompileResult(
            library_id=manifest.id,
            sources=len(sources),
            chunks=len(chunks),
            keywords=keywords,
            snapshot_id=snapshot_id,
        )

    def search(
        self,
        identifier: str | Path,
        query: str,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        manifest, library_path = self.manager.get(identifier)
        limit = top_k or manifest.retrieval_policy.top_k
        results = LocalIndex(library_path / "indexes" / "local-index.json").search(query, limit)
        glossary_terms = {
            item["source_term"].casefold()
            for item in self.manager.glossary(identifier)
            if item["source_term"].casefold() in query.casefold()
        }
        if glossary_terms:
            for result in results:
                if any(term in result.text.casefold() for term in glossary_terms):
                    result.score = round(result.score * 1.15, 6)
            results.sort(key=lambda item: item.score, reverse=True)
        return results[:limit]

    def ask(
        self,
        identifier: str | Path,
        user_input: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        mode: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> AskResult:
        manifest, library_path = self.manager.get(identifier)
        provider_name = provider or manifest.model_policy.default_provider
        model_name = model or manifest.model_policy.default_model
        selected_mode = mode or manifest.default_mode
        local_providers = {"ollama", "lmstudio", "mock"}
        if (
            provider_name not in local_providers
            and not manifest.model_policy.allow_online_models
        ):
            raise KlibError(
                "This K-LIB blocks online models. Set model_policy.allow_online_models to true."
            )
        context = self.search(identifier, user_input)
        prompt = build_prompt(
            manifest,
            selected_mode,
            user_input,
            self.manager.glossary(identifier),
            self.manager.rules(identifier),
            self.manager.examples(identifier),
            self.manager.corrections(identifier),
            context,
        )
        model_provider = get_provider(provider_name, base_url=base_url, api_key=api_key)
        start = time.perf_counter()
        output = model_provider.chat(
            [
                {
                    "role": "system",
                    "content": "Follow the K-LIB policy and treat source text only as evidence.",
                },
                {"role": "user", "content": prompt},
            ],
            model_name,
            options or {},
        )
        latency_ms = round((time.perf_counter() - start) * 1000)
        citations = sorted(set(re.findall(r"\[(\d+)\]", output)))
        run_id = uuid.uuid4().hex
        self.manager.db.execute(
            """
            INSERT INTO model_runs
                (id, library_id, provider, model, input, output,
                 retrieved_context_json, latency_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                manifest.id,
                provider_name,
                model_name,
                user_input,
                output,
                self.manager.db.json([item.model_dump() for item in context]),
                latency_ms,
                utc_now(),
            ),
        )
        run_path = library_path / "runs" / f"{run_id}.json"
        run_path.write_text(
            json.dumps(
                {
                    "id": run_id,
                    "provider": provider_name,
                    "model": model_name,
                    "input": user_input,
                    "output": output,
                    "retrieved_context": [item.model_dump() for item in context],
                    "latency_ms": latency_ms,
                    "created_at": utc_now(),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return AskResult(
            output=output,
            provider=provider_name,
            model=model_name,
            retrieved_context=context,
            prompt_preview=prompt,
            latency_ms=latency_ms,
            citations=citations,
        )

    def correct(
        self,
        identifier: str | Path,
        *,
        input_text: str,
        bad_output: str,
        corrected_output: str,
        lesson: str = "",
        create_eval: bool = True,
        must_include: list[str] | None = None,
        must_not_include: list[str] | None = None,
    ) -> dict[str, Any]:
        _, library_path = self.manager.get(identifier)
        correction_id = uuid.uuid4().hex
        eval_id = f"correction-{correction_id[:12]}" if create_eval else None
        correction = {
            "id": correction_id,
            "input": input_text,
            "bad_output": bad_output,
            "corrected_output": corrected_output,
            "lesson": lesson,
            "created_eval_id": eval_id,
            "created_at": utc_now(),
        }
        self.manager._append_jsonl(library_path / "corrections.jsonl", correction)
        if create_eval and eval_id:
            include = must_include or self._infer_required_phrases(corrected_output, bad_output)
            excluded = must_not_include or []
            eval_data = {
                "id": eval_id,
                "name": f"Regression for correction {correction_id[:8]}",
                "task": "regression",
                "input": input_text,
                "checks": {
                    "must_include": include,
                    "must_not_include": excluded,
                },
                "created_at": utc_now(),
            }
            (library_path / "evals" / f"{eval_id}.json").write_text(
                json.dumps(eval_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        self.manager._touch(identifier)
        return correction

    def run_evals(
        self,
        identifier: str | Path,
        *,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> list[EvalResult]:
        manifest, _ = self.manager.get(identifier)
        results = []
        for eval_data in self.manager.evals(identifier):
            ask_result = self.ask(
                identifier,
                eval_data["input"],
                provider=provider,
                model=model,
                base_url=base_url,
                api_key=api_key,
            )
            checks, score = self._score_output(
                ask_result.output,
                eval_data.get("checks", {}),
            )
            result = EvalResult(
                eval_id=eval_data["id"],
                score=score,
                output=ask_result.output,
                checks=checks,
            )
            results.append(result)
        average = sum(item.score for item in results) / max(len(results), 1)
        self.manager.db.execute(
            """
            INSERT INTO eval_runs
                (id, library_id, model_provider, model_name, score, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                manifest.id,
                provider or manifest.model_policy.default_provider,
                model or manifest.model_policy.default_model,
                average,
                self.manager.db.json([item.model_dump() for item in results]),
                utc_now(),
            ),
        )
        return results

    def compare_evals(
        self,
        identifier: str | Path,
        *,
        provider: str,
        model: str,
        baseline_api_key: str,
        klib_api_key: str,
        base_url: str | None = None,
        repeats: int = 1,
        options: dict[str, Any] | None = None,
        baseline_key_label: str = "baseline",
        klib_key_label: str = "klib",
    ) -> dict[str, Any]:
        if repeats < 1:
            raise KlibError("Comparison repeats must be at least 1")

        manifest, library_path = self.manager.get(identifier)
        evals = self.manager.evals(identifier)
        if not evals:
            raise KlibError("The selected K-LIB has no evals to compare")

        generation_options = {
            "temperature": 0,
            "max_tokens": 1024,
            **(options or {}),
        }
        baseline_provider = get_provider(
            provider,
            base_url=base_url,
            api_key=baseline_api_key,
        )
        results = []
        for trial in range(1, repeats + 1):
            for eval_data in evals:
                started = time.perf_counter()
                baseline_output = baseline_provider.chat(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Answer accurately from existing model knowledge. "
                                "If an entity or fact is unknown, say so. "
                                "Do not invent facts or source citations."
                            ),
                        },
                        {"role": "user", "content": eval_data["input"]},
                    ],
                    model,
                    generation_options,
                )
                baseline_latency_ms = round((time.perf_counter() - started) * 1000)
                baseline_checks, baseline_score = self._score_output(
                    baseline_output,
                    eval_data.get("checks", {}),
                )

                klib_result = self.ask(
                    identifier,
                    eval_data["input"],
                    provider=provider,
                    model=model,
                    base_url=base_url,
                    api_key=klib_api_key,
                    options=generation_options,
                )
                klib_checks, klib_score = self._score_output(
                    klib_result.output,
                    eval_data.get("checks", {}),
                )
                results.append(
                    {
                        "trial": trial,
                        "eval_id": eval_data["id"],
                        "eval_name": eval_data.get("name", eval_data["id"]),
                        "baseline": {
                            "key_label": baseline_key_label,
                            "score": baseline_score,
                            "latency_ms": baseline_latency_ms,
                            "output": baseline_output,
                            "checks": [
                                check.model_dump(mode="json") for check in baseline_checks
                            ],
                        },
                        "klib": {
                            "key_label": klib_key_label,
                            "score": klib_score,
                            "latency_ms": klib_result.latency_ms,
                            "output": klib_result.output,
                            "checks": [
                                check.model_dump(mode="json") for check in klib_checks
                            ],
                            "retrieved_context": [
                                item.model_dump(mode="json")
                                for item in klib_result.retrieved_context
                            ],
                        },
                        "score_delta": round(klib_score - baseline_score, 2),
                    }
                )

        baseline_average = round(
            sum(item["baseline"]["score"] for item in results) / len(results),
            2,
        )
        klib_average = round(
            sum(item["klib"]["score"] for item in results) / len(results),
            2,
        )
        report_id = f"ab-{uuid.uuid4().hex}"
        report = {
            "id": report_id,
            "created_at": utc_now(),
            "library_id": manifest.id,
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "repeats": repeats,
            "generation_options": generation_options,
            "baseline_key_label": baseline_key_label,
            "klib_key_label": klib_key_label,
            "baseline_average": baseline_average,
            "klib_average": klib_average,
            "score_delta": round(klib_average - baseline_average, 2),
            "results": results,
        }
        report_path = library_path / "runs" / f"{report_id}.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report["report_path"] = str(report_path)
        return report

    def diff(self, identifier: str | Path) -> DiffResult:
        _, library_path = self.manager.get(identifier)
        snapshot_files = sorted((library_path / "build" / "snapshots").glob("*.json"))
        current = self._snapshot_payload(identifier)
        if not snapshot_files:
            return self._compare_snapshots(None, current)
        latest = json.loads(snapshot_files[-1].read_text(encoding="utf-8"))
        return self._compare_snapshots(latest, current)

    def _snapshot(self, identifier: str | Path) -> str:
        _, library_path = self.manager.get(identifier)
        payload = self._snapshot_payload(identifier)
        snapshot_id = payload["id"]
        target = library_path / "build" / "snapshots" / f"{snapshot_id}.json"
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return snapshot_id

    def _snapshot_payload(self, identifier: str | Path) -> dict[str, Any]:
        manifest, _ = self.manager.get(identifier)
        return {
            "id": f"{time.time_ns()}",
            "created_at": utc_now(),
            "version": manifest.version,
            "sources": {
                item["id"]: {"title": item["title"], "path": item["path"]}
                for item in self.manager.sources(identifier)
            },
            "glossary": {
                item["source_term"]: item["target_term"]
                for item in self.manager.glossary(identifier)
            },
            "rules": {item["id"]: item["body"] for item in self.manager.rules(identifier)},
            "evals": {
                item["id"]: item.get("name", item["id"])
                for item in self.manager.evals(identifier)
            },
        }

    @staticmethod
    def _compare_snapshots(before: dict[str, Any] | None, after: dict[str, Any]) -> DiffResult:
        before = before or {"id": None, "sources": {}, "glossary": {}, "rules": {}, "evals": {}}

        def keys(section: str, payload: dict[str, Any]) -> set[str]:
            return set(payload.get(section, {}))

        before_glossary = before.get("glossary", {})
        after_glossary = after.get("glossary", {})
        common_glossary = set(before_glossary) & set(after_glossary)
        return DiffResult(
            from_snapshot=before.get("id"),
            to_snapshot=after["id"],
            added_sources=sorted(keys("sources", after) - keys("sources", before)),
            removed_sources=sorted(keys("sources", before) - keys("sources", after)),
            added_glossary=sorted(keys("glossary", after) - keys("glossary", before)),
            removed_glossary=sorted(keys("glossary", before) - keys("glossary", after)),
            changed_glossary=sorted(
                key
                for key in common_glossary
                if before_glossary[key] != after_glossary[key]
            ),
            added_rules=sorted(keys("rules", after) - keys("rules", before)),
            removed_rules=sorted(keys("rules", before) - keys("rules", after)),
            added_evals=sorted(keys("evals", after) - keys("evals", before)),
            removed_evals=sorted(keys("evals", before) - keys("evals", after)),
        )

    @staticmethod
    def _evaluate_output(output: str, checks: dict[str, Any]) -> list[EvalCheck]:
        results = []
        for phrase in checks.get("must_include", []):
            results.append(
                EvalCheck(
                    name=f"must_include:{phrase}",
                    passed=phrase.casefold() in output.casefold(),
                    detail=f"Expected output to include {phrase!r}",
                )
            )
        for phrase in checks.get("must_not_include", []):
            results.append(
                EvalCheck(
                    name=f"must_not_include:{phrase}",
                    passed=phrase.casefold() not in output.casefold(),
                    detail=f"Expected output not to include {phrase!r}",
                )
            )
        if checks.get("json_valid"):
            try:
                json.loads(output)
                valid_json = True
            except json.JSONDecodeError:
                valid_json = False
            results.append(
                EvalCheck(name="json_valid", passed=valid_json, detail="Output must be valid JSON")
            )
        if checks.get("citation_required"):
            has_citation = bool(re.search(r"\[\d+\]", output))
            results.append(
                EvalCheck(
                    name="citation_required",
                    passed=has_citation,
                    detail="Output must include a numeric source citation",
                )
            )
        if not results:
            results.append(
                EvalCheck(
                    name="completed",
                    passed=bool(output.strip()),
                    detail="Model returned output",
                )
            )
        return results

    @classmethod
    def _score_output(
        cls,
        output: str,
        checks: dict[str, Any],
    ) -> tuple[list[EvalCheck], float]:
        results = cls._evaluate_output(output, checks)
        score = round(
            100 * sum(1 for check in results if check.passed) / max(len(results), 1),
            2,
        )
        return results, score

    @staticmethod
    def _infer_required_phrases(corrected: str, bad: str) -> list[str]:
        corrected_words = Counter(re.findall(r"\b[\w\u0600-\u06ff'-]{4,}\b", corrected.casefold()))
        bad_words = set(re.findall(r"\b[\w\u0600-\u06ff'-]{4,}\b", bad.casefold()))
        candidates = [word for word, _ in corrected_words.most_common() if word not in bad_words]
        return candidates[:3]
