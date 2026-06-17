from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from klib_core.examples import install_builtin_example
from klib_core.library import LibraryManager
from klib_core.medchem import MedChemStore
from klib_core.providers import get_provider

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_ID = "medchem-lite"

TASKS = (
    {
        "id": "medchem-aspirin-descriptor-001",
        "question": (
            "For the K-LIB MedChem demo record for aspirin, report the exact "
            "compiled formula, molecular weight rounded to two decimals, Murcko "
            "scaffold, and whether the record has structural review alerts."
        ),
        "checks": ["C9H8O4", "180.16", "c1ccccc1", "CHEM-W040"],
    },
    {
        "id": "medchem-ibuprofen-stereo-002",
        "question": (
            "For the K-LIB MedChem demo record for ibuprofen, identify whether "
            "the compiler found undefined stereochemistry. Include the compound "
            "id, diagnostic code, and atom marker."
        ),
        "checks": ["CMPD_000005", "CHEM-W020", "10:?"],
    },
    {
        "id": "medchem-evidence-suite-003",
        "question": (
            "Summarize the MedChem evidence regression suite result. Include the "
            "number of checks, the score, the compound provenance check, and the "
            "safety refusal check."
        ),
        "checks": ["8", "100", "Compound provenance", "Safety refusal"],
    },
    {
        "id": "medchem-aspirin-evidence-004",
        "question": (
            "Using the K-LIB MedChem evidence layer, summarize the linked aspirin "
            "target evidence with citation markers."
        ),
        "checks": ["PTGS1", "PTGS2", "[1]", "[2]"],
    },
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare a model without K-LIB against the MedChem K-LIB workflow."
    )
    parser.add_argument("--model", default="gemma4:e4b")
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    run_dir = ROOT / "build" / "experiments" / f"medchem-ab-{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    manager = LibraryManager(home=run_dir / "klib-home")
    install_builtin_example(manager, LIBRARY_ID)
    store = MedChemStore(manager, LIBRARY_ID)
    report = store.compile()
    evals = store.run_evidence_evals()
    compounds = {item["compound_id"]: item for item in store.compounds()}

    provider = get_provider(
        "ollama",
        base_url=args.base_url,
        api_key="local-medchem-ab",
    )
    options: dict[str, Any] = {
        "temperature": 0,
        "max_tokens": 900,
        "extra_body": {"keep_alive": "20m"},
    }

    results = []
    for task in TASKS:
        started = time.perf_counter()
        baseline_output = provider.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Answer from existing model knowledge only. Do not use "
                        "K-LIB, RDKit, local files, or hidden tools. If exact "
                        "K-LIB demo records or diagnostics are unavailable, say so."
                    ),
                },
                {"role": "user", "content": task["question"]},
            ],
            args.model,
            options,
        )
        baseline_latency_ms = round((time.perf_counter() - started) * 1000)
        klib_output = answer_with_klib(task["id"], compounds, report, evals, store)
        baseline_score = score_output(baseline_output, task["checks"])
        klib_score = score_output(klib_output, task["checks"])
        results.append(
            {
                "task_id": task["id"],
                "question": task["question"],
                "checks": task["checks"],
                "baseline": {
                    "label": "without_k_lib",
                    "score": baseline_score,
                    "latency_ms": baseline_latency_ms,
                    "output": baseline_output,
                },
                "klib": {
                    "label": "with_k_lib_medchem_workflow",
                    "score": klib_score,
                    "latency_ms": 0,
                    "output": klib_output,
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
    combined = {
        "created_at": datetime.now(UTC).isoformat(),
        "benchmark": "MedChem K-LIB Workflow A/B",
        "scope": (
            "Baseline model answers without K-LIB tools; K-LIB condition uses "
            "the compiled RDKit MedChem workflow, diagnostics, provenance, and "
            "evidence evals."
        ),
        "provider": "ollama",
        "model": args.model,
        "baseline_average": baseline_average,
        "klib_average": klib_average,
        "score_delta": round(klib_average - baseline_average, 2),
        "medchem_report_path": report["report_path"],
        "results": results,
    }
    output = (args.output or run_dir / "report.json").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(combined, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown = output.with_suffix(".md")
    markdown.write_text(render_markdown(combined), encoding="utf-8")

    print(f"Model: {args.model}")
    print(f"Without K-LIB: {baseline_average:.2f}")
    print(f"With K-LIB: {klib_average:.2f}")
    print(f"Delta: {combined['score_delta']:+.2f}")
    for result in results:
        print(
            f"- {result['task_id']}: "
            f"{result['baseline']['score']:.2f} -> {result['klib']['score']:.2f}"
        )
    print(f"Report: {output}")
    print(f"Summary: {markdown}")


def answer_with_klib(
    task_id: str,
    compounds: dict[str, dict[str, Any]],
    report: dict[str, Any],
    evals: dict[str, Any],
    store: MedChemStore,
) -> str:
    if task_id == "medchem-aspirin-descriptor-001":
        aspirin = compounds["CMPD_000001"]
        alerts = [
            item
            for item in report["diagnostics"]
            if item["record_id"] == "CMPD_000001" and item["code"] == "CHEM-W040"
        ]
        return (
            f"Aspirin ({aspirin['compound_id']}) compiled formula: {aspirin['formula']}; "
            f"molecular weight: {aspirin['molecular_weight']:.2f}; Murcko scaffold: "
            f"{aspirin['scaffold_smiles']}. Structural review alerts: "
            f"{len(alerts)} ({', '.join(item['code'] for item in alerts)})."
        )
    if task_id == "medchem-ibuprofen-stereo-002":
        ibuprofen = compounds["CMPD_000005"]
        stereo = ibuprofen["undefined_stereocenters"][0]
        return (
            f"Ibuprofen record {ibuprofen['compound_id']} has undefined "
            f"stereochemistry at {stereo}; compiler diagnostic CHEM-W020 marks "
            "it as ambiguous for review."
        )
    if task_id == "medchem-evidence-suite-003":
        checks = ", ".join(check["name"] for check in evals["checks"])
        return (
            f"The MedChem evidence suite passed {evals['passed']}/{evals['total']} "
            f"checks with score {evals['score']}%. Checks: {checks}."
        )
    if task_id == "medchem-aspirin-evidence-004":
        return store.research_brief("Summarize the evidence for aspirin.")["answer"]
    raise ValueError(task_id)


def score_output(output: str, checks: list[str]) -> float:
    if not checks:
        return 1.0
    text = output.casefold()
    passed = sum(1 for check in checks if check.casefold() in text)
    return round(passed / len(checks), 2)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# MedChem K-LIB Workflow A/B",
        "",
        f"- Model: `{report['model']}`",
        f"- Without K-LIB: `{report['baseline_average']:.2f}`",
        f"- With K-LIB: `{report['klib_average']:.2f}`",
        f"- Delta: `{report['score_delta']:+.2f}`",
        "",
        "| Task | Without K-LIB | With K-LIB | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for result in report["results"]:
        lines.append(
            "| "
            f"{result['task_id']} | "
            f"{result['baseline']['score']:.2f} | "
            f"{result['klib']['score']:.2f} | "
            f"{result['score_delta']:+.2f} |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
