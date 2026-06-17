from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from klib_core.engine import ForgeEngine
from klib_core.library import LibraryManager
from klib_core.providers import get_provider

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_ID = "biology-core-reference"
TASK = "internal_protocol_recall"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare a local model without and with the fictional Aster-9 private-knowledge layer."
        )
    )
    parser.add_argument("--model", default="gemma4:e4b")
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manager = LibraryManager()
    engine = ForgeEngine(manager)
    evals = [item for item in manager.evals(LIBRARY_ID) if item.get("task") == TASK]
    if not evals:
        raise SystemExit(f"No {TASK!r} evaluations found in {LIBRARY_ID}")

    options: dict[str, Any] = {
        "temperature": 0,
        "max_tokens": 700,
        "extra_body": {"keep_alive": "20m"},
    }
    provider = get_provider(
        "ollama",
        base_url=args.base_url,
        api_key="local-private-ab",
    )
    results = []

    for eval_data in evals:
        started = time.perf_counter()
        baseline_output = provider.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Answer only from existing model knowledge. If the "
                        "fictional internal protocol is unknown, say so. Do not "
                        "guess values or invent citations."
                    ),
                },
                {"role": "user", "content": eval_data["input"]},
            ],
            args.model,
            options,
        )
        baseline_latency_ms = round((time.perf_counter() - started) * 1000)
        baseline_checks, baseline_score = engine._score_output(
            baseline_output,
            eval_data.get("checks", {}),
        )

        grounded = engine.ask(
            LIBRARY_ID,
            eval_data["input"],
            provider="ollama",
            model=args.model,
            base_url=args.base_url,
            api_key="local-private-ab",
            options=options,
        )
        klib_checks, klib_score = engine._score_output(
            grounded.output,
            eval_data.get("checks", {}),
        )
        results.append(
            {
                "eval_id": eval_data["id"],
                "input": eval_data["input"],
                "baseline": {
                    "score": baseline_score,
                    "latency_ms": baseline_latency_ms,
                    "output": baseline_output,
                    "checks": [check.model_dump(mode="json") for check in baseline_checks],
                },
                "klib": {
                    "score": klib_score,
                    "latency_ms": grounded.latency_ms,
                    "output": grounded.output,
                    "checks": [check.model_dump(mode="json") for check in klib_checks],
                    "retrieved_sources": sorted(
                        {item.source_title for item in grounded.retrieved_context}
                    ),
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
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "library_id": LIBRARY_ID,
        "scope": (
            "Four questions about a clearly fictional internal biology protocol "
            "that is absent from model pretraining."
        ),
        "model": args.model,
        "provider": "ollama",
        "baseline_average": baseline_average,
        "klib_average": klib_average,
        "score_delta": round(klib_average - baseline_average, 2),
        "results": results,
    }

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    output = (
        args.output or ROOT / "build" / "experiments" / f"biology-private-ab-{timestamp}.json"
    ).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Model: {args.model}")
    print(f"Without K-LIB: {baseline_average:.2f}")
    print(f"With K-LIB: {klib_average:.2f}")
    print(f"Delta: {report['score_delta']:+.2f}")
    for result in results:
        print(
            f"- {result['eval_id']}: "
            f"{result['baseline']['score']:.2f} -> {result['klib']['score']:.2f}"
        )
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
