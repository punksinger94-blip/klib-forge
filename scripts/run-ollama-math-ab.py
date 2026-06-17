from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from klib_core.engine import ForgeEngine
from klib_core.library import LibraryManager
from klib_core.manifest import save_manifest

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ID = "kestrel-applied-math-benchmark"

MATH_SPECIFICATION = """# Kestrel Applied Math Standard

This is a fictional mathematical specification created only for a controlled
baseline-versus-K-LIB evaluation. Its named formulas are not public conventions.

## Aster loss-adjusted yield

For initial yield P, loss percentage r, and humidity index h, calculate:

Y = P * (1 - r / 100)^2 * (1 - h / 500)

Keep full precision during substitution and round only the final result to three
decimal places.

## Nemor thermal load

For module count n and temperature rise dT, calculate:

Q = n * (1.8 * dT + 0.012 * dT^2)

Report Q to one decimal place when needed.

## Velar normalized distance

For coordinates x and y, scale constants a and b, and multiplier c, calculate:

D = c * sqrt((x / a)^2 + (y / b)^2)

Round the final result to two decimal places.

## Quenby reserve recurrence

Start with reserve R_0. For each completed cycle, apply:

R_(t+1) = 1.06 * R_t - 3

Do not round intermediate cycles. Round only the requested final reserve to two
decimal places.

## Algebra control

Ordinary algebra questions labeled as controls do not use a named Kestrel
formula. Solve them directly from the equation supplied in the question.
"""

EVALS = (
    {
        "id": "math-aster-001",
        "name": "Apply the Aster loss-adjusted yield formula",
        "task": "grounded_applied_math",
        "input": (
            "Under the Kestrel Aster protocol, calculate the loss-adjusted yield "
            "for P = 240, r = 7.5%, and h = 40. Show the substituted calculation, "
            "give the final result using the required rounding rule, and cite the "
            "supplied specification."
        ),
        "checks": {
            "must_include": ["188.922"],
            "citation_required": True,
        },
    },
    {
        "id": "math-nemor-002",
        "name": "Apply the Nemor thermal-load formula",
        "task": "grounded_applied_math",
        "input": (
            "Using the Kestrel Nemor definition, compute Q for n = 14 modules and "
            "dT = 25. Show the per-module subtotal and final thermal load, and cite "
            "the supplied specification."
        ),
        "checks": {
            "must_include": ["52.5", "735"],
            "citation_required": True,
        },
    },
    {
        "id": "math-velar-003",
        "name": "Apply the Velar normalized-distance formula",
        "task": "grounded_applied_math",
        "input": (
            "Under the Kestrel Velar protocol, calculate D when x = 6, y = 8, "
            "a = 3, b = 4, and c = 12. Show the simplified square-root term, apply "
            "the required rounding rule, and cite the supplied specification."
        ),
        "checks": {
            "must_include": ["33.94"],
            "must_include_any": [["sqrt(8)", "sqrt{8}", "√8", "2.828"]],
            "citation_required": True,
        },
    },
    {
        "id": "math-quenby-004",
        "name": "Apply the Quenby reserve recurrence",
        "task": "grounded_applied_math",
        "input": (
            "Using the Kestrel Quenby recurrence with R_0 = 80, calculate the "
            "reserve after four completed cycles. Show R_1 and the final R_4, "
            "follow the rounding rule, and cite the supplied specification."
        ),
        "checks": {
            "must_include": ["81.8", "87.87"],
            "citation_required": True,
        },
    },
    {
        "id": "math-control-005",
        "name": "Ordinary algebra control",
        "task": "algebra_control",
        "input": (
            "Control problem: solve 3x + 7 = 28. Show one rearrangement step and "
            "state the final value of x."
        ),
        "checks": {
            "must_include_any": [["x = 7", "x=7"]],
        },
    },
)


def install_benchmark(manager: LibraryManager, run_dir: Path, model: str) -> Path:
    manifest = manager.create(
        "Kestrel Applied Math Benchmark",
        library_id=BENCHMARK_ID,
        description=(
            "Controlled applied-math benchmark with fictional named formulas "
            "and one ordinary algebra control."
        ),
        domain="mathematics/applied-benchmark",
    )
    _, library_path = manager.get(BENCHMARK_ID)
    manifest.languages = ["en"]
    manifest.default_mode = "grounded_applied_math"
    manifest.supported_tasks = ["grounded_applied_math", "algebra_control"]
    manifest.retrieval_policy.top_k = 3
    manifest.retrieval_policy.require_citations = True
    manifest.model_policy.default_provider = "ollama"
    manifest.model_policy.default_model = model
    manifest.model_policy.allow_online_models = False
    save_manifest(library_path, manifest)
    manager.register(library_path)

    manager.add_rule(
        BENCHMARK_ID,
        "Use the exact named formula and rounding rule in the retrieved specification.",
        title="Use the supplied formula",
        priority=1,
    )
    manager.add_rule(
        BENCHMARK_ID,
        "Show a compact substitution before the final numeric answer.",
        title="Show the calculation",
        priority=2,
    )
    manager.add_rule(
        BENCHMARK_ID,
        "Do not invent a definition when a named formula is absent from the evidence.",
        title="Do not invent formulas",
        priority=3,
    )
    manager.add_rule(
        BENCHMARK_ID,
        "Keep the complete calculation under 180 words.",
        title="Be concise",
        priority=4,
    )

    source_path = run_dir / "kestrel-applied-math-standard.md"
    source_path.write_text(MATH_SPECIFICATION, encoding="utf-8")
    manager.add_sources(BENCHMARK_ID, source_path)
    for eval_data in EVALS:
        manager.save_eval(BENCHMARK_ID, eval_data)

    ForgeEngine(manager).compile(BENCHMARK_ID)
    return library_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare a local Ollama model without and with a math K-LIB."
    )
    parser.add_argument("--model", default="gemma4:e4b")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON report path. Defaults to a timestamped experiment folder.",
    )
    args = parser.parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    run_dir = ROOT / "build" / "experiments" / f"ollama-math-ab-{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    manager = LibraryManager(home=run_dir / "klib-home")
    library_path = install_benchmark(manager, run_dir, args.model)

    report = ForgeEngine(manager).compare_evals(
        BENCHMARK_ID,
        provider="ollama",
        model=args.model,
        baseline_api_key="local-baseline",
        klib_api_key="local-klib",
        base_url="http://localhost:11434/v1",
        repeats=args.repeats,
        options={
            "temperature": 0,
            "max_tokens": 2048,
            "extra_body": {"keep_alive": "20m"},
        },
        baseline_key_label="OLLAMA_NO_KLIB",
        klib_key_label="OLLAMA_WITH_KLIB",
    )
    combined = {
        "benchmark": "Kestrel Applied Math",
        "benchmark_scope": (
            "Four fictional named-formula tasks test grounded specification "
            "retrieval plus calculation; one ordinary algebra task is a control."
        ),
        "model": args.model,
        "provider": "ollama",
        "library_path": str(library_path),
        "report": report,
    }
    output = (args.output or (run_dir / "report.json")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(combined, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Model: {args.model}")
    print(f"Without K-LIB: {report['baseline_average']:.2f}")
    print(f"With K-LIB: {report['klib_average']:.2f}")
    print(f"Delta: {report['score_delta']:+.2f}")
    for result in report["results"]:
        print(
            f"- {result['eval_id']}: "
            f"{result['baseline']['score']:.2f} -> {result['klib']['score']:.2f}"
        )
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
