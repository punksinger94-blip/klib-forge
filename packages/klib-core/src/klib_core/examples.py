from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .benchmarks import LITERATURE_BIOLOGY_EVALS, LITERATURE_BIOLOGY_SOURCES
from .engine import ForgeEngine
from .errors import LibraryNotFoundError
from .library import LibraryManager
from .manifest import save_manifest

INCIDENT_SOURCES = (
    (
        "payment-api-incident.md",
        """# Payment API incident record INC-2026-041

On 2026-04-18 at 09:12 UTC, payment authorization error rate rose from 0.3%
to 18.7% after release payments-api 4.18.0. The first alert fired at 09:15 UTC.
The incident commander was Mina Chen. The team disabled the new adaptive retry
policy at 09:24 UTC and error rate returned below 1% at 09:29 UTC.

The proximate cause was retry amplification against the card-network adapter.
The release changed the maximum retry count from two to six and omitted jitter.
No data was lost, but 12,481 authorization attempts failed before recovery.
""",
    ),
    (
        "payment-api-runbook.md",
        """# Payment API production runbook

For authorization error rate above 5% for five minutes, declare SEV-1, appoint
an incident commander, freeze deployments, and compare the current release with
the last known good version. Prefer disabling a feature flag over database
rollback when the fault is isolated to optional behavior.

Recovery requires error rate below 1% for ten continuous minutes. Before
closing the incident, reconcile failed authorization attempts, publish a
customer-impact statement, and create owners for every corrective action.
""",
    ),
    (
        "reliability-policy.md",
        """# Reliability and evidence policy

The payment authorization service has a 99.95% monthly availability objective.
Incident summaries must distinguish observed evidence, working hypotheses, and
confirmed causes. Never invent a customer-impact count. When records conflict,
quote both values and flag the conflict for human review.
""",
    ),
)

INCIDENT_EVALS = (
    {
        "id": "incident-timeline-001",
        "name": "Reconstruct the production timeline",
        "task": "incident_analysis",
        "input": (
            "Reconstruct INC-2026-041 from first observed degradation through recovery, "
            "including exact UTC times and the mitigation. Cite the evidence."
        ),
        "checks": {
            "must_include": ["09:12", "09:24", "09:29", "adaptive retry"],
            "citation_required": True,
        },
    },
    {
        "id": "incident-cause-002",
        "name": "Separate cause from impact",
        "task": "incident_analysis",
        "input": (
            "State the confirmed proximate cause, the release involved, and the measured "
            "customer impact for INC-2026-041. Cite the evidence."
        ),
        "checks": {
            "must_include": ["4.18.0", "12,481", "retry"],
            "citation_required": True,
        },
    },
    {
        "id": "incident-runbook-003",
        "name": "Apply the recovery policy",
        "task": "incident_analysis",
        "input": (
            "What conditions must be satisfied before this payment incident can be "
            "closed, and which follow-up actions are mandatory? Cite the runbook."
        ),
        "checks": {
            "must_include": ["below 1%", "ten", "reconcile", "customer-impact"],
            "citation_required": True,
        },
    },
)

EXAMPLE_CATALOG = (
    {
        "id": "biomedical-evidence-synthesis",
        "name": "Biomedical Evidence Synthesis",
        "description": (
            "Answer quantitative biology questions from five curated primary studies "
            "with exact identifiers, scoped claims, citations, and regression evals."
        ),
        "domain": "biology/primary-literature",
        "source_count": len(LITERATURE_BIOLOGY_SOURCES),
        "eval_count": len(LITERATURE_BIOLOGY_EVALS),
    },
    {
        "id": "production-incident-response",
        "name": "Production Incident Response",
        "description": (
            "Reconstruct a payment outage, separate evidence from hypotheses, apply "
            "a recovery runbook, and verify the result with deterministic evals."
        ),
        "domain": "reliability/incident-response",
        "source_count": len(INCIDENT_SOURCES),
        "eval_count": len(INCIDENT_EVALS),
    },
)


def list_builtin_examples() -> list[dict[str, Any]]:
    return [dict(item) for item in EXAMPLE_CATALOG]


def install_builtin_example(
    manager: LibraryManager,
    example_id: str,
) -> tuple[bool, Path]:
    if example_id not in {item["id"] for item in EXAMPLE_CATALOG}:
        raise LibraryNotFoundError(f"Unknown built-in example: {example_id}")
    try:
        _, path = manager.get(example_id)
        return False, path
    except LibraryNotFoundError:
        pass

    path = (
        _install_biomedical(manager)
        if example_id == "biomedical-evidence-synthesis"
        else _install_incident(manager)
    )
    ForgeEngine(manager).compile(example_id)
    return True, path


def _create_library(
    manager: LibraryManager,
    *,
    library_id: str,
    name: str,
    description: str,
    domain: str,
    mode: str,
) -> Path:
    manifest = manager.create(
        name,
        library_id=library_id,
        description=description,
        domain=domain,
    )
    _, path = manager.get(library_id)
    manifest.languages = ["en"]
    manifest.default_mode = mode
    manifest.supported_tasks = [mode]
    manifest.retrieval_policy.top_k = 5
    manifest.model_policy.default_provider = "mock"
    manifest.model_policy.default_model = "offline-demo"
    save_manifest(path, manifest)
    manager.register(path)
    return path


def _add_sources(
    manager: LibraryManager,
    library_id: str,
    sources: tuple[tuple[str, str], ...],
) -> None:
    with tempfile.TemporaryDirectory() as temporary_dir:
        source_dir = Path(temporary_dir)
        for filename, content in sources:
            (source_dir / filename).write_text(content, encoding="utf-8")
        manager.add_sources(library_id, source_dir)


def _install_biomedical(manager: LibraryManager) -> Path:
    library_id = "biomedical-evidence-synthesis"
    path = _create_library(
        manager,
        library_id=library_id,
        name="Biomedical Evidence Synthesis",
        description=str(EXAMPLE_CATALOG[0]["description"]),
        domain=str(EXAMPLE_CATALOG[0]["domain"]),
        mode="primary_literature_fact_check",
    )
    manager.add_rule(
        library_id,
        "Answer only from retrieved primary-study evidence and cite every factual claim.",
        title="Ground every claim",
        priority=1,
    )
    manager.add_rule(
        library_id,
        "Preserve exact organisms, strains, molecules, units, and quantitative identifiers.",
        title="Preserve study details",
        priority=2,
    )
    manager.add_rule(
        library_id,
        "Do not generalize a paper-specific result beyond its reported experiment.",
        title="Respect evidence scope",
        priority=3,
    )
    manager.add_example(
        library_id,
        "Report the UPEC temperature-shift design and transcriptome result.",
        (
            "CFT073 cells were shifted from 23 C to 37 C for 4 hours; at the stated "
            "threshold, mRNA expression changed for 9% of the genome [1]."
        ),
        task="primary_literature_fact_check",
        mode="primary_literature_fact_check",
    )
    _add_sources(manager, library_id, LITERATURE_BIOLOGY_SOURCES)
    for eval_data in LITERATURE_BIOLOGY_EVALS:
        manager.save_eval(library_id, eval_data)
    return path


def _install_incident(manager: LibraryManager) -> Path:
    library_id = "production-incident-response"
    path = _create_library(
        manager,
        library_id=library_id,
        name="Production Incident Response",
        description=str(EXAMPLE_CATALOG[1]["description"]),
        domain=str(EXAMPLE_CATALOG[1]["domain"]),
        mode="incident_analysis",
    )
    manager.add_glossary(
        library_id,
        "SEV-1",
        "Highest-severity production incident",
        notes="Use only when the runbook threshold is met.",
    )
    manager.add_rule(
        library_id,
        "Separate observed evidence, working hypotheses, and confirmed causes.",
        title="Label certainty",
        priority=1,
    )
    manager.add_rule(
        library_id,
        "Preserve timestamps, versions, percentages, and customer-impact counts exactly.",
        title="Preserve incident facts",
        priority=2,
    )
    manager.add_rule(
        library_id,
        "Apply closure criteria from the runbook and identify any unmet requirement.",
        title="Verify recovery",
        priority=3,
    )
    manager.add_example(
        library_id,
        "What restored service?",
        (
            "The team disabled the adaptive retry policy at 09:24 UTC; the authorization "
            "error rate returned below 1% at 09:29 UTC [1]."
        ),
        task="incident_analysis",
        mode="incident_analysis",
    )
    _add_sources(manager, library_id, INCIDENT_SOURCES)
    for eval_data in INCIDENT_EVALS:
        manager.save_eval(library_id, eval_data)
    return path
