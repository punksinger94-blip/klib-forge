from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .engine import ForgeEngine
from .errors import LibraryNotFoundError
from .library import LibraryManager
from .manifest import save_manifest

BIOLOGY_BENCHMARK_ID = "vesperomyces-biology-benchmark"
BIOLOGY_BENCHMARK_MODEL = "meta/llama-3.3-70b-instruct"

BIOLOGY_SOURCE = """# Vesperomyces marina reference dossier

Vesperomyces marina is a fictional marine microorganism created solely for
controlled K-LIB evaluation. The facts in this dossier do not describe a real
organism.

## Nitrogen metabolism

The enzyme Luma reductase, encoded by the gene LurA, converts nitrite to
ammonium only when the surrounding pH is below 6.4. The regulatory protein Brx7
represses LurA expression when dissolved oxygen rises above 3.2 mg/L.

## Culture conditions

The reference culture uses a salinity of 28 ppt and a temperature of 17 C.
Healthy cultures emit amber fluorescence at 590 nm during stationary phase.

## Contamination check

Growth at 37 C combined with the absence of amber fluorescence at 590 nm is the
benchmark's contamination signature. Either observation alone is insufficient.
"""

BIOLOGY_EVALS = (
    {
        "id": "biology-nitrogen-001",
        "name": "Identify the fictional nitrite reduction mechanism",
        "task": "biological_fact_check",
        "input": (
            "For Vesperomyces marina, name the gene encoding the enzyme that converts "
            "nitrite to ammonium and state the required pH threshold. Cite the source."
        ),
        "checks": {
            "must_include": ["LurA", "6.4"],
            "citation_required": True,
        },
    },
    {
        "id": "biology-regulation-002",
        "name": "Identify the fictional oxygen-dependent regulator",
        "task": "biological_fact_check",
        "input": (
            "What protein represses LurA in Vesperomyces marina, and above what "
            "dissolved-oxygen value does repression occur? Cite the source."
        ),
        "checks": {
            "must_include": ["Brx7", "3.2"],
            "citation_required": True,
        },
    },
    {
        "id": "biology-culture-003",
        "name": "Recover the fictional reference culture conditions",
        "task": "biological_fact_check",
        "input": (
            "State the reference salinity and temperature for Vesperomyces marina. "
            "Cite the source."
        ),
        "checks": {
            "must_include": ["28", "17"],
            "citation_required": True,
        },
    },
    {
        "id": "biology-contamination-004",
        "name": "Recover the two-part fictional contamination signature",
        "task": "biological_fact_check",
        "input": (
            "Which two observations together indicate contamination in the "
            "Vesperomyces marina benchmark? Cite the source."
        ),
        "checks": {
            "must_include": ["37", "590"],
            "citation_required": True,
        },
    },
)


def install_biology_benchmark(
    manager: LibraryManager,
    *,
    model: str = BIOLOGY_BENCHMARK_MODEL,
) -> Path:
    try:
        manifest, library_path = manager.get(BIOLOGY_BENCHMARK_ID)
    except LibraryNotFoundError:
        manifest = manager.create(
            "Vesperomyces Biology Benchmark",
            library_id=BIOLOGY_BENCHMARK_ID,
            description=(
                "Synthetic biology facts for controlled baseline-versus-K-LIB evaluation."
            ),
            domain="biology/synthetic-benchmark",
        )
        _, library_path = manager.get(BIOLOGY_BENCHMARK_ID)
        manifest.languages = ["en"]
        manifest.default_mode = "biological_fact_check"
        manifest.supported_tasks = ["biological_fact_check"]
        manifest.retrieval_policy.top_k = 4
        manifest.model_policy.default_provider = "nvidia"
        manifest.model_policy.default_model = model
        manifest.model_policy.allow_online_models = True
        save_manifest(library_path, manifest)
        manager.register(library_path)

        manager.add_rule(
            BIOLOGY_BENCHMARK_ID,
            "Use only facts supported by the retrieved Vesperomyces reference dossier.",
            title="Ground answers in the benchmark",
            priority=1,
        )
        manager.add_rule(
            BIOLOGY_BENCHMARK_ID,
            "State when the retrieved source does not contain the requested fact.",
            title="Do not fill evidence gaps",
            priority=2,
        )

        with tempfile.TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "vesperomyces-reference.md"
            source_path.write_text(BIOLOGY_SOURCE, encoding="utf-8")
            manager.add_sources(BIOLOGY_BENCHMARK_ID, source_path)

        for eval_data in BIOLOGY_EVALS:
            target = library_path / "evals" / f"{eval_data['id']}.json"
            target.write_text(
                json.dumps(eval_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    ForgeEngine(manager).compile(BIOLOGY_BENCHMARK_ID)
    return library_path
