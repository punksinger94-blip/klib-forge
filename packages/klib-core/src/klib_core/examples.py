from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .benchmarks import LITERATURE_BIOLOGY_EVALS, LITERATURE_BIOLOGY_SOURCES
from .engine import ForgeEngine
from .errors import LibraryNotFoundError
from .library import LibraryManager
from .manifest import save_manifest
from .medchem import (
    MEDCHEM_LITE_DESCRIPTION,
    MedChemStore,
    initialize_medchem_library,
)

MEDCHEM_COMPOUNDS_CSV = (
    "compound_id,name,smiles,synonyms,source_refs,status\n"
    "CMPD_000001,Aspirin,CC(=O)Oc1ccccc1C(=O)O,acetylsalicylic acid,"
    "example_reference,research_reference_only\n"
    "CMPD_000002,Salicylic acid,O=C(O)c1ccccc1O,2-hydroxybenzoic acid,"
    "example_reference,research_reference_only\n"
    "CMPD_000003,Acetaminophen,CC(=O)NC1=CC=C(O)C=C1,paracetamol,"
    "example_reference,research_reference_only\n"
    "CMPD_000004,Caffeine,Cn1c(=O)c2c(ncn2C)n(C)c1=O,"
    "1 3 7-trimethylxanthine,example_reference,research_reference_only\n"
    "CMPD_000005,Ibuprofen,CC(C)Cc1ccc(cc1)C(C)C(=O)O,"
    "2-(4-isobutylphenyl)propionic acid,example_reference,research_reference_only\n"
    "CMPD_000006,Invalid example,C1(CC,deliberately invalid,"
    "example_validation,research_reference_only\n"
)

MEDCHEM_TARGETS = (
    {
        "target_id": "TGT_PTGS1",
        "name": "Prostaglandin G/H synthase 1",
        "gene_symbol": "PTGS1",
        "organism": "Homo sapiens",
        "accession": "P23219",
        "description": "Cyclooxygenase-1; constitutive prostaglandin synthesis enzyme.",
    },
    {
        "target_id": "TGT_PTGS2",
        "name": "Prostaglandin G/H synthase 2",
        "gene_symbol": "PTGS2",
        "organism": "Homo sapiens",
        "accession": "P35354",
        "description": "Cyclooxygenase-2; inducible prostaglandin synthesis enzyme.",
    },
    {
        "target_id": "TGT_ADORA2A",
        "name": "Adenosine A2A receptor",
        "gene_symbol": "ADORA2A",
        "organism": "Homo sapiens",
        "accession": "P29274",
        "description": "G-protein coupled adenosine receptor.",
    },
)

MEDCHEM_ENVIRONMENTS = (
    {
        "environment_id": "ENV_BIOCHEM_BUFFER_001",
        "name": "Buffered in-vitro enzyme assay",
        "environment_type": "in_vitro",
        "lab_name": "K-LIB teaching lab",
        "biosafety_level": "BSL-1",
        "temperature_c": "37",
        "ph": "7.4",
        "buffer": "phosphate-buffered assay medium",
        "assay_platform": "plate-reader biochemical assay",
        "instrument": "UV/fluorescence plate reader",
        "notes": "Educational assay context for enzyme inhibition records.",
    },
    {
        "environment_id": "ENV_REVIEW_CONTEXT_001",
        "name": "Literature review evidence context",
        "environment_type": "literature_review",
        "lab_name": "curated literature notes",
        "notes": "Non-experimental context used for review-derived mechanism records.",
    },
)

MEDCHEM_ACTIVITIES = (
    {
        "activity_id": "ACT_ASPIRIN_PTGS1_001",
        "compound_id": "CMPD_000001",
        "target_id": "TGT_PTGS1",
        "assay_type": "biochemical mechanism",
        "environment_id": "ENV_BIOCHEM_BUFFER_001",
        "endpoint": "inhibition",
        "relation": "=",
        "value": "50",
        "unit": "% at 100 uM after 15 min",
        "result": "Aspirin acetylation tracked with prostaglandin synthase inhibition",
        "source_ids": ["LIT_ROTH_1975"],
        "source_locator": "demo activity record; Roth 1975 mechanism evidence",
        "evidence_quote": "50% inhibition at 100 uM after 15 min",
        "evidence_note": (
            "The original experiment used microsomal enzyme preparations; this demo "
            "activity stores 50% inhibition at 100 uM after 15 min as the value anchor."
        ),
    },
    {
        "activity_id": "ACT_ASPIRIN_PG_002",
        "compound_id": "CMPD_000001",
        "target_id": "TGT_PTGS2",
        "assay_type": "prostaglandin synthesis",
        "environment_id": "ENV_REVIEW_CONTEXT_001",
        "endpoint": "mechanism",
        "result": "Aspirin-like drugs inhibited prostaglandin synthesis",
        "source_ids": ["LIT_VANE_1971"],
        "source_locator": "demo activity record; Vane 1971 mechanism evidence",
        "evidence_quote": "Aspirin-like drugs inhibited prostaglandin synthesis",
        "evidence_note": "Historical mechanism evidence; not a clinical efficacy record.",
    },
    {
        "activity_id": "ACT_CAFFEINE_A2A_001",
        "compound_id": "CMPD_000004",
        "target_id": "TGT_ADORA2A",
        "assay_type": "receptor pharmacology review",
        "environment_id": "ENV_REVIEW_CONTEXT_001",
        "endpoint": "mechanism",
        "result": "Caffeine acts primarily through antagonism of adenosine receptors",
        "source_ids": ["LIT_FREDHOLM_1999"],
        "source_locator": "demo activity record; Fredholm 1999 review evidence",
        "evidence_quote": "antagonism of adenosine receptors",
        "evidence_note": "Review evidence covering central nervous system actions.",
    },
    {
        "activity_id": "ACT_ACETAMINOPHEN_PTGS1_001",
        "compound_id": "CMPD_000003",
        "target_id": "TGT_PTGS1",
        "assay_type": "mechanism review",
        "environment_id": "ENV_REVIEW_CONTEXT_001",
        "endpoint": "context-dependent inhibition",
        "result": "Acetaminophen can reduce prostaglandin synthesis through the peroxidase site",
        "source_ids": ["LIT_ANDERSON_2008"],
        "source_locator": "demo activity record; Anderson 2008 mechanism evidence",
        "evidence_quote": "peroxide-tone-dependent effects at prostaglandin H2 synthetase",
        "evidence_note": "The effect depends on cellular peroxide tone and substrate context.",
    },
    {
        "activity_id": "ACT_ACETAMINOPHEN_PTGS2_002",
        "compound_id": "CMPD_000003",
        "target_id": "TGT_PTGS2",
        "assay_type": "mechanism review",
        "environment_id": "ENV_REVIEW_CONTEXT_001",
        "endpoint": "context-dependent inhibition",
        "result": "Acetaminophen cyclooxygenase inhibition is physiologically nuanced",
        "source_ids": ["LIT_ANDERSON_2008"],
        "source_locator": "demo activity record; Anderson 2008 mechanism evidence",
        "evidence_quote": "mechanism is multifactorial",
        "evidence_note": "The record intentionally preserves mechanistic uncertainty.",
    },
)

MEDCHEM_LITERATURE = (
    {
        "source_id": "LIT_VANE_1971",
        "title": "Inhibition of prostaglandin synthesis as a mechanism of action",
        "citation": "Vane JR. Nat New Biol. 1971;231:232-235. PMID: 5284360.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/5284360/",
        "year": "1971",
        "evidence_summary": (
            "Aspirin-like drugs inhibited prostaglandin synthesis, supporting a "
            "mechanistic explanation for their pharmacological actions."
        ),
    },
    {
        "source_id": "LIT_ROTH_1975",
        "title": "Acetylation of prostaglandin synthase by aspirin",
        "citation": (
            "Roth GJ, Stanford N, Majerus PW. Proc Natl Acad Sci USA. "
            "1975;72:3073-3076. PMID: 810797."
        ),
        "url": "https://pubmed.ncbi.nlm.nih.gov/810797/",
        "year": "1975",
        "evidence_summary": (
            "Aspirin acetylated a prostaglandin synthase protein, and acetylation "
            "tracked with cyclooxygenase inhibition in the reported experiment. The "
            "demo activity value anchor is 50% inhibition at 100 uM after 15 min."
        ),
    },
    {
        "source_id": "LIT_FREDHOLM_1999",
        "title": "Actions of caffeine in the brain",
        "citation": (
            "Fredholm BB et al. Pharmacol Rev. 1999;51:83-133. PMID: 10049999."
        ),
        "url": "https://pubmed.ncbi.nlm.nih.gov/10049999/",
        "year": "1999",
        "evidence_summary": (
            "The review identifies antagonism of adenosine receptors as the primary "
            "mechanism underlying common central actions of caffeine."
        ),
    },
    {
        "source_id": "LIT_ANDERSON_2008",
        "title": "Paracetamol (Acetaminophen): mechanisms of action",
        "citation": (
            "Anderson BJ. Paediatr Anaesth. 2008;18:915-921. PMID: 18811827."
        ),
        "url": "https://pubmed.ncbi.nlm.nih.gov/18811827/",
        "year": "2008",
        "evidence_summary": (
            "The review describes peroxide-tone-dependent effects at prostaglandin "
            "H2 synthetase and emphasizes that acetaminophen mechanism is multifactorial."
        ),
    },
)

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
    {
        "id": "medchem-lite",
        "name": "MedChem-KLIB Lite",
        "description": MEDCHEM_LITE_DESCRIPTION,
        "domain": "chemistry/medicinal-chemistry",
        "source_count": 6,
        "eval_count": 0,
        "requires_extra": "medchem",
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
        if example_id == "medchem-lite":
            _install_medchem_compounds(manager)
            _install_medchem_evidence(manager, path)
            MedChemStore(manager, example_id).compile()
        return False, path
    except LibraryNotFoundError:
        pass

    if example_id == "biomedical-evidence-synthesis":
        path = _install_biomedical(manager)
        ForgeEngine(manager).compile(example_id)
    elif example_id == "production-incident-response":
        path = _install_incident(manager)
        ForgeEngine(manager).compile(example_id)
    else:
        path = _install_medchem(manager)
        MedChemStore(manager, example_id).compile()
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


def _install_medchem(manager: LibraryManager) -> Path:
    library_id = "medchem-lite"
    _, path = initialize_medchem_library(
        manager,
        "MedChem-KLIB Lite",
        library_id=library_id,
    )
    manager.add_rule(
        library_id,
        "Use RDKit-derived structure fields and do not invent chemical properties.",
        title="Validate chemistry with tools",
        priority=1,
    )
    manager.add_rule(
        library_id,
        (
            "Do not provide synthesis instructions, dosage recommendations, "
            "clinical decisions, or harmful-compound optimization."
        ),
        title="Keep outputs research-only",
        priority=2,
    )
    _install_medchem_compounds(manager)
    _install_medchem_evidence(manager, path)
    return path


def _install_medchem_compounds(manager: LibraryManager) -> None:
    with tempfile.TemporaryDirectory() as temporary_dir:
        source = Path(temporary_dir) / "compounds.csv"
        source.write_text(MEDCHEM_COMPOUNDS_CSV, encoding="utf-8")
        MedChemStore(manager, "medchem-lite").import_compounds(source)


def _install_medchem_evidence(manager: LibraryManager, path: Path) -> None:
    store = MedChemStore(manager, "medchem-lite")
    with tempfile.TemporaryDirectory() as temporary_dir:
        temporary = Path(temporary_dir)
        targets = temporary / "targets.jsonl"
        environments = temporary / "environments.jsonl"
        activities = temporary / "activities.jsonl"
        literature = temporary / "literature.jsonl"
        for output, records in (
            (targets, MEDCHEM_TARGETS),
            (environments, MEDCHEM_ENVIRONMENTS),
            (activities, MEDCHEM_ACTIVITIES),
            (literature, MEDCHEM_LITERATURE),
        ):
            output.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
        store.import_targets(targets)
        store.import_environments(environments)
        store.import_bioactivity(activities)
        store.import_literature(literature)
    manager.update_manifest(
        path,
        {
            "description": MEDCHEM_LITE_DESCRIPTION,
            "knowledge_ir_version": "medchem-ir-preview.1",
            "validator_profile": {
                "id": "rdkit-medchem-preview",
                "domain": "chemistry/medicinal-chemistry",
                "engine": "RDKit",
                "passes": [
                    "standardize_identity",
                    "stereochemistry",
                    "descriptors",
                    "structural_alerts",
                    "activity_normalization",
                    "referential_integrity",
                    "provenance",
                    "safety",
                ],
            },
        },
    )
