from __future__ import annotations

import csv
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

from .errors import KlibError
from .library import LibraryManager
from .manifest import save_manifest
from .models import utc_now
from .providers import get_provider

SUPPORTED_COMPOUND_FORMATS = {".csv", ".jsonl", ".sdf", ".smi", ".txt"}
RESEARCH_STATUS = "research_reference_only"
MEDCHEM_IR_VERSION = "medchem-ir-preview.1"
MEDCHEM_VALIDATOR_PROFILE = "rdkit-medchem-preview"
CONCENTRATION_UNITS = {
    "m": 1.0,
    "mm": 1e-3,
    "um": 1e-6,
    "µm": 1e-6,
    "μm": 1e-6,
    "nm": 1e-9,
    "pm": 1e-12,
}
PACTIVITY_ENDPOINTS = {"ic50", "ec50", "ac50", "ki", "kd", "potency"}
MEDCHEM_SOURCE_CATALOG = {
    "pubchem": {
        "name": "PubChem",
        "scope": "large public compound database",
        "access": "PUG-REST",
        "license": "public-domain/us-government-open-data",
        "commercial_use": "allowed_with_attribution_practice",
        "recommended_use": "default live enrichment source for release demos",
        "release_phase": "P1 active",
        "release_scope": "small live imports and curated subsets",
        "url": "https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest",
        "status": "active",
    },
    "chembl": {
        "name": "ChEMBL",
        "scope": "curated bioactivity for drug-like molecules",
        "access": "REST web services and bulk downloads",
        "license": "open-data-check-current-ebi-terms",
        "commercial_use": "check-current-terms",
        "recommended_use": "bioactivity/target enrichment after PubChem identity import",
        "release_phase": "P2 planned",
        "release_scope": "target-linked activity subsets with assay normalization",
        "url": "https://www.ebi.ac.uk/chembl/api/data/docs",
        "status": "planned",
    },
    "cas_common_chemistry": {
        "name": "CAS Common Chemistry",
        "scope": "curated common and regulated substances",
        "access": "search site and API by request",
        "license": "CC BY-NC 4.0",
        "commercial_use": "not allowed without separate commercial license",
        "recommended_use": "non-commercial academic packages only",
        "release_phase": "P3 restricted",
        "release_scope": "opt-in academic connector after license review",
        "url": "https://commonchemistry.cas.org/",
        "status": "planned_restricted",
    },
    "zinc": {
        "name": "ZINC",
        "scope": "commercially available virtual-screening compounds",
        "access": "download subsets",
        "license": "check-current-zinc-terms",
        "commercial_use": "check-current-terms",
        "recommended_use": "screening subsets, never full mirror by default",
        "release_phase": "P3 planned",
        "release_scope": "curated screening subsets and 3D-ready records",
        "url": "https://zinc.docking.org/",
        "status": "planned",
    },
    "epa_comptox": {
        "name": "EPA CompTox Chemicals Dashboard",
        "scope": "environmental chemistry and toxicity-oriented identifiers",
        "access": "download/API resources",
        "license": "check-current-epa-terms",
        "commercial_use": "check-current-terms",
        "recommended_use": "safety/toxicity context, not optimization",
        "release_phase": "P3 planned",
        "release_scope": "identifier and safety-context enrichment",
        "url": "https://comptox.epa.gov/dashboard/",
        "status": "planned",
    },
}
DESCRIPTOR_METHODS = {
    "standardization": (
        "RDKit MolStandardize LargestFragmentChooser, Normalizer, Uncharger, "
        "and TautomerEnumerator"
    ),
    "identity": "RDKit canonical SMILES, InChI, and InChIKey",
    "molecular_weight": "RDKit Descriptors.MolWt",
    "exact_molecular_weight": "RDKit Descriptors.ExactMolWt",
    "formula": "RDKit rdMolDescriptors.CalcMolFormula",
    "logp": "RDKit Crippen.MolLogP (cLogP)",
    "hbd": "RDKit Lipinski.NumHDonors",
    "hba": "RDKit Lipinski.NumHAcceptors",
    "tpsa": "RDKit rdMolDescriptors.CalcTPSA",
    "rotatable_bonds": "RDKit rdMolDescriptors.CalcNumRotatableBonds",
    "ring_count": "RDKit rdMolDescriptors.CalcNumRings",
    "fraction_csp3": "RDKit rdMolDescriptors.CalcFractionCSP3",
    "scaffold_smiles": "RDKit MurckoScaffold.MurckoScaffoldSmiles",
    "fingerprint": "RDKit Morgan fingerprint radius 2, 2048 bits",
    "stereochemistry": "RDKit Chem.FindMolChiralCenters includeUnassigned=True",
    "structural_alerts": "RDKit FilterCatalog PAINS, BRENK, and NIH review filters",
}
MEDCHEM_LITE_DESCRIPTION = (
    "MedChem-KLIB Lite turns molecular structures, scaffolds, compound properties, "
    "bioactivity records, and literature notes into a safe, testable AI research library."
)

MEDCHEM_DIRECTORIES = (
    "compounds",
    "scaffolds",
    "environments",
    "targets",
    "bioactivity",
    "literature",
    "indexes/fingerprint_index",
)

REFUSAL = (
    "I can help validate structures, calculate descriptors, compare known "
    "molecules, summarize evidence, and flag research risks, but I cannot "
    "provide synthesis instructions, human dosing advice, or harmful-compound "
    "optimization."
)


def rdkit_available() -> bool:
    try:
        import rdkit  # noqa: F401
    except ImportError:
        return False
    return True


def require_rdkit() -> None:
    if not rdkit_available():
        raise KlibError(
            "MedChem-KLIB requires RDKit. Install the optional dependency with "
            '`pip install "klib-forge[medchem]"`.'
        )


def initialize_medchem_library(
    manager: LibraryManager,
    name: str,
    *,
    library_id: str | None = None,
    path: Path | None = None,
) -> tuple[Any, Path]:
    manifest = manager.create(
        name,
        library_id=library_id,
        description=MEDCHEM_LITE_DESCRIPTION,
        domain="chemistry/medicinal-chemistry",
        path=path,
    )
    _, library_path = manager.get(manifest.id)
    manifest.default_mode = "medchem_evidence"
    manifest.knowledge_ir_version = MEDCHEM_IR_VERSION
    manifest.validator_profile = {
        "id": MEDCHEM_VALIDATOR_PROFILE,
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
    }
    manifest.supported_tasks = [
        "compound_validation",
        "descriptor_analysis",
        "scaffold_comparison",
        "evidence_grounding",
        "safety_refusal",
    ]
    manifest.model_policy.allow_online_models = False
    manifest.retrieval_policy.require_citations = True
    save_manifest(library_path, manifest)
    for directory in MEDCHEM_DIRECTORIES:
        (library_path / directory).mkdir(parents=True, exist_ok=True)
    (library_path / "compounds" / "compounds.jsonl").touch()
    (library_path / "scaffolds" / "scaffolds.jsonl").touch()
    (library_path / "environments" / "environments.jsonl").touch()
    (library_path / "bioactivity" / "activities.jsonl").touch()
    (library_path / "targets" / "targets.jsonl").touch()
    (library_path / "literature" / "notes.md").write_text(
        "# MedChem literature notes\n", encoding="utf-8"
    )
    (library_path / "policies" / "medchem_safety_policy.json").write_text(
        json.dumps(
            {
                "status": "research_only",
                "blocked": [
                    "synthesis_instructions",
                    "human_dosage_advice",
                    "clinical_decision_making",
                    "controlled_substance_optimization",
                    "toxin_or_poison_optimization",
                    "pathogen_or_biohazard_optimization",
                ],
                "allowed": [
                    "structure_validation",
                    "descriptor_calculation",
                    "similarity_search",
                    "scaffold_comparison",
                    "evidence_summary",
                    "risk_flagging",
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    manager.register(library_path)
    return manifest, library_path


class MedChemStore:
    def __init__(self, manager: LibraryManager, identifier: str | Path):
        self.manager = manager
        self.manifest, self.path = manager.get(identifier)
        if not self.manifest.domain.startswith("chemistry/"):
            raise KlibError(
                f"Library is not a MedChem package: {self.manifest.id} "
                f"(domain={self.manifest.domain})"
            )
        for directory in MEDCHEM_DIRECTORIES:
            (self.path / directory).mkdir(parents=True, exist_ok=True)

    @property
    def compounds_path(self) -> Path:
        return self.path / "compounds" / "compounds.jsonl"

    @property
    def compiled_path(self) -> Path:
        return self.path / "build" / "medchem_compounds.jsonl"

    @property
    def targets_path(self) -> Path:
        return self.path / "targets" / "targets.jsonl"

    @property
    def environments_path(self) -> Path:
        return self.path / "environments" / "environments.jsonl"

    @property
    def activities_path(self) -> Path:
        return self.path / "bioactivity" / "activities.jsonl"

    @property
    def literature_path(self) -> Path:
        return self.path / "literature" / "records.jsonl"

    def import_compounds(self, source: Path) -> dict[str, Any]:
        source = source.expanduser().resolve()
        if not source.is_file():
            raise KlibError(f"Compound source is not a file: {source}")
        if source.suffix.casefold() not in SUPPORTED_COMPOUND_FORMATS:
            supported = ", ".join(sorted(SUPPORTED_COMPOUND_FORMATS))
            raise KlibError(f"Unsupported compound format. Expected one of: {supported}")

        existing = self._read_jsonl(self.compounds_path)
        by_id = {str(item["compound_id"]): item for item in existing}
        next_number = self._next_compound_number(existing)
        imported = 0
        updated = 0
        for raw in self._read_source(source):
            record = self._normalize_record(raw, source, next_number)
            next_number += 1
            if record["compound_id"] in by_id:
                updated += 1
            else:
                imported += 1
            by_id[record["compound_id"]] = record

        records = list(by_id.values())
        self._write_jsonl(self.compounds_path, records)
        return {
            "library_id": self.manifest.id,
            "source": str(source),
            "imported": imported,
            "updated": updated,
            "total": len(records),
            "status": RESEARCH_STATUS,
        }

    def import_pubchem(
        self,
        identifiers: list[str],
        *,
        namespace: str = "name",
        synonyms_limit: int = 12,
    ) -> dict[str, Any]:
        if namespace not in {"name", "cid"}:
            raise KlibError("PubChem namespace must be 'name' or 'cid'")
        identifiers = [item.strip() for item in identifiers if item.strip()]
        if not identifiers:
            raise KlibError("At least one PubChem identifier is required")

        existing = self._read_jsonl(self.compounds_path)
        by_id = {str(item["compound_id"]): item for item in existing}
        imported = 0
        updated = 0
        failures = []
        for identifier in identifiers:
            try:
                record = fetch_pubchem_compound(
                    identifier,
                    namespace=namespace,
                    synonyms_limit=synonyms_limit,
                )
            except KlibError as exc:
                failures.append({"identifier": identifier, "error": str(exc)})
                continue
            if record["compound_id"] in by_id:
                updated += 1
            else:
                imported += 1
            by_id[record["compound_id"]] = record

        self._write_jsonl(self.compounds_path, by_id.values())
        return {
            "library_id": self.manifest.id,
            "provider": "pubchem",
            "namespace": namespace,
            "requested": len(identifiers),
            "imported": imported,
            "updated": updated,
            "failed": len(failures),
            "failures": failures,
            "total": len(by_id),
            "license": MEDCHEM_SOURCE_CATALOG["pubchem"]["license"],
            "status": RESEARCH_STATUS,
        }

    def validate(self) -> dict[str, Any]:
        require_rdkit()

        valid = []
        invalid = []
        for record in self._read_jsonl(self.compounds_path):
            smiles = str(record.get("smiles", "")).strip()
            molecule = standardize_molecule(smiles)
            result = {
                "compound_id": record["compound_id"],
                "name": record.get("name", ""),
                "smiles": smiles,
            }
            if molecule is None:
                result["error"] = "RDKit could not parse the SMILES"
                invalid.append(result)
            else:
                result.update(identity_for_molecule(molecule))
                if result["canonical_smiles"] != _canonical_smiles(smiles):
                    result["standardized"] = True
                valid.append(result)
        return {
            "library_id": self.manifest.id,
            "total": len(valid) + len(invalid),
            "valid": len(valid),
            "invalid": len(invalid),
            "valid_compounds": valid,
            "invalid_compounds": invalid,
        }

    def compile(self) -> dict[str, Any]:
        require_rdkit()
        from rdkit import rdBase

        compiled = []
        invalid = []
        diagnostics = []
        inchikey_counts: dict[str, int] = {}
        scaffold_counts: dict[str, int] = {}
        inchikey_records: dict[str, list[str]] = {}
        for record in self._read_jsonl(self.compounds_path):
            smiles = str(record.get("smiles", "")).strip()
            molecule = standardize_molecule(smiles)
            if molecule is None:
                invalid_record = {
                    "compound_id": record["compound_id"],
                    "name": record.get("name", ""),
                    "smiles": smiles,
                    "error": "RDKit could not parse the SMILES",
                }
                invalid.append(invalid_record)
                diagnostics.append(
                    _diagnostic(
                        "error",
                        "CHEM-E001",
                        str(record["compound_id"]),
                        "smiles",
                        "RDKit could not parse the SMILES; record excluded.",
                    )
                )
                continue
            result = {**record, **describe_molecule(smiles)}
            compiled_at = utc_now()
            original_canonical = _canonical_smiles(smiles)
            if original_canonical and original_canonical != result["canonical_smiles"]:
                diagnostics.append(
                    _diagnostic(
                        "warning",
                        "CHEM-W010",
                        str(record["compound_id"]),
                        "smiles",
                        (
                            "Input structure was standardized before identity and "
                            "descriptor calculation."
                        ),
                    )
                )
            for stereocenter in result["undefined_stereocenters"]:
                diagnostics.append(
                    _diagnostic(
                        "warning",
                        "CHEM-W020",
                        str(record["compound_id"]),
                        "stereochemistry",
                        (
                            f"Undefined stereocenter detected at atom {stereocenter}; "
                            "stereochemistry was preserved as ambiguous for review."
                        ),
                    )
                )
            for alert in result["structural_alerts"]:
                diagnostics.append(
                    _diagnostic(
                        "warning",
                        "CHEM-W040",
                        str(record["compound_id"]),
                        "structure_alert",
                        (
                            f"Structural alert matched {alert['name']} "
                            f"({alert['filter_set']}); treat as a review flag, not a verdict."
                        ),
                    )
                )
            result["compiled_at"] = compiled_at
            result["provenance"] = _compound_provenance(
                record,
                result,
                compiled_at=compiled_at,
                standardized=bool(
                    original_canonical
                    and original_canonical != result["canonical_smiles"]
                ),
            )
            compiled.append(result)
            inchikey = result["inchikey"]
            inchikey_counts[inchikey] = inchikey_counts.get(inchikey, 0) + 1
            inchikey_records.setdefault(inchikey, []).append(str(record["compound_id"]))
            scaffold = result["scaffold_smiles"]
            if scaffold:
                scaffold_counts[scaffold] = scaffold_counts.get(scaffold, 0) + 1

        scaffolds = [
            {"scaffold_smiles": scaffold, "compound_count": count}
            for scaffold, count in sorted(
                scaffold_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ]
        self._write_jsonl(self.path / "scaffolds" / "scaffolds.jsonl", scaffolds)
        duplicate_inchikeys = sorted(key for key, count in inchikey_counts.items() if count > 1)
        duplicate_identity_groups = []
        for inchikey in duplicate_inchikeys:
            group_records = [
                record for record in compiled if record.get("inchikey") == inchikey
            ]
            primary = next(
                (
                    record
                    for record in group_records
                    if not str(record.get("compound_id", "")).startswith("PUBCHEM_CID_")
                ),
                group_records[0],
            )
            group = {
                "inchikey": inchikey,
                "compound_ids": [str(record["compound_id"]) for record in group_records],
                "names": [str(record["name"]) for record in group_records],
                "sources": sorted(
                    {
                        str(record.get("source_database") or "local")
                        for record in group_records
                    }
                ),
                "records": [
                    {
                        "compound_id": str(record["compound_id"]),
                        "name": str(record["name"]),
                        "source_database": record.get("source_database") or "local",
                        "source_url": record.get("source_url"),
                        "source_license": record.get("source_license"),
                        "external_ids": record.get("external_ids") or {},
                    }
                    for record in group_records
                ],
                "primary_compound_id": str(primary["compound_id"]),
                "resolution": "linked_for_review",
                "recommended_action": (
                    "Use the primary record as the stable package compound and merge "
                    "source-specific aliases, external IDs, and provenance after review."
                ),
            }
            duplicate_identity_groups.append(group)
            for record in group_records:
                record["identity_group"] = {
                    "inchikey": inchikey,
                    "compound_ids": group["compound_ids"],
                    "primary_compound_id": group["primary_compound_id"],
                    "resolution": group["resolution"],
                }
            diagnostics.append(
                _diagnostic(
                    "warning",
                    "CHEM-W011",
                    ",".join(inchikey_records[inchikey]),
                    "inchikey",
                    f"Standardized structures share identity key {inchikey}.",
                )
            )
        self._write_jsonl(self.compiled_path, compiled)
        report = {
            "library_id": self.manifest.id,
            "rdkit_version": rdBase.rdkitVersion,
            "knowledge_ir_version": MEDCHEM_IR_VERSION,
            "validator_profile": MEDCHEM_VALIDATOR_PROFILE,
            "input_compounds": len(compiled) + len(invalid),
            "valid_compounds": len(compiled),
            "invalid_compounds": len(invalid),
            "unique_scaffolds": len(scaffolds),
            "duplicate_inchikeys": duplicate_inchikeys,
            "duplicate_identity_groups": duplicate_identity_groups,
            "invalid_records": invalid,
            "diagnostics": diagnostics,
            "compiled_at": utc_now(),
            "status": RESEARCH_STATUS,
        }
        report_path = self.path / "build" / "medchem_compile_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report["report_path"] = str(report_path)
        return report

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        needle = query.casefold().strip()
        if not needle:
            raise KlibError("Search query cannot be empty")
        records = self._compiled_records()
        matches = []
        for record in records:
            haystack = " ".join(
                [
                    str(record.get("compound_id", "")),
                    str(record.get("name", "")),
                    str(record.get("canonical_smiles", "")),
                    str(record.get("inchikey", "")),
                    " ".join(record.get("synonyms", [])),
                ]
            ).casefold()
            if needle in haystack:
                matches.append(record)
        return matches[:limit]

    def compounds(self, *, compiled: bool = True) -> list[dict[str, Any]]:
        if compiled:
            return self._compiled_records()
        return self._read_jsonl(self.compounds_path)

    def compile_report(self) -> dict[str, Any] | None:
        report_path = self.path / "build" / "medchem_compile_report.json"
        if not report_path.exists():
            return None
        try:
            value = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise KlibError(f"Invalid MedChem compile report: {exc}") from exc
        if not isinstance(value, dict):
            raise KlibError("MedChem compile report must be a JSON object")
        value["report_path"] = str(report_path)
        return value

    def import_targets(self, source: Path) -> dict[str, Any]:
        records = []
        for raw in self._read_evidence_source(source):
            lowered = {str(key).strip().casefold(): value for key, value in raw.items()}
            target_id = str(lowered.get("target_id") or "").strip()
            name = str(lowered.get("name") or "").strip()
            if not target_id or not name:
                raise KlibError("Target records require target_id and name")
            records.append(
                {
                    "record_type": "target",
                    "ir_version": MEDCHEM_IR_VERSION,
                    "target_id": target_id,
                    "name": name,
                    "gene_symbol": str(lowered.get("gene_symbol") or "").strip(),
                    "organism": str(lowered.get("organism") or "").strip(),
                    "accession": str(lowered.get("accession") or "").strip(),
                    "description": str(lowered.get("description") or "").strip(),
                    "status": RESEARCH_STATUS,
                }
            )
        result = self._merge_records(self.targets_path, records, "target_id")
        return {"library_id": self.manifest.id, **result}

    def import_environments(self, source: Path) -> dict[str, Any]:
        records = []
        for raw in self._read_evidence_source(source):
            lowered = {str(key).strip().casefold(): value for key, value in raw.items()}
            environment_id = str(
                lowered.get("environment_id")
                or lowered.get("env_id")
                or lowered.get("test_environment_id")
                or ""
            ).strip()
            name = str(lowered.get("name") or "").strip()
            if not environment_id or not name:
                raise KlibError("Environment records require environment_id and name")
            records.append(
                {
                    "record_type": "test_environment",
                    "ir_version": MEDCHEM_IR_VERSION,
                    "environment_id": environment_id,
                    "name": name,
                    "environment_type": str(
                        lowered.get("environment_type")
                        or lowered.get("type")
                        or "wet_lab"
                    ).strip(),
                    "lab_name": str(lowered.get("lab_name") or "").strip(),
                    "biosafety_level": str(
                        lowered.get("biosafety_level") or lowered.get("bsl") or ""
                    ).strip(),
                    "temperature_c": str(lowered.get("temperature_c") or "").strip(),
                    "ph": str(lowered.get("ph") or lowered.get("pH") or "").strip(),
                    "solvent": str(lowered.get("solvent") or "").strip(),
                    "buffer": str(lowered.get("buffer") or "").strip(),
                    "cell_line": str(lowered.get("cell_line") or "").strip(),
                    "organism": str(lowered.get("organism") or "").strip(),
                    "assay_platform": str(lowered.get("assay_platform") or "").strip(),
                    "instrument": str(lowered.get("instrument") or "").strip(),
                    "notes": str(lowered.get("notes") or "").strip(),
                    "status": RESEARCH_STATUS,
                }
            )
        result = self._merge_records(
            self.environments_path,
            records,
            "environment_id",
        )
        return {"library_id": self.manifest.id, **result}

    def import_bioactivity(self, source: Path) -> dict[str, Any]:
        records = []
        for raw in self._read_evidence_source(source):
            lowered = {str(key).strip().casefold(): value for key, value in raw.items()}
            compound_id = str(lowered.get("compound_id") or "").strip()
            target_id = str(lowered.get("target_id") or "").strip()
            if not compound_id or not target_id:
                raise KlibError("Bioactivity records require compound_id and target_id")
            activity = {
                "record_type": "activity",
                "ir_version": MEDCHEM_IR_VERSION,
                "activity_id": str(
                    lowered.get("activity_id") or f"ACT_{uuid.uuid4().hex[:12]}"
                ).strip(),
                "compound_id": compound_id,
                "target_id": target_id,
                "assay_type": str(lowered.get("assay_type") or "").strip(),
                "assay_format": str(lowered.get("assay_format") or "").strip(),
                "environment_id": str(
                    lowered.get("environment_id")
                    or lowered.get("env_id")
                    or lowered.get("test_environment_id")
                    or ""
                ).strip(),
                "endpoint": str(lowered.get("endpoint") or "").strip(),
                "relation": str(lowered.get("relation") or "=").strip(),
                "value": str(lowered.get("value") or "").strip(),
                "unit": str(lowered.get("unit") or "").strip(),
                "result": str(lowered.get("result") or "").strip(),
                "source_ids": _as_list(
                    lowered.get("source_ids") or lowered.get("source_id")
                ),
                "source_locator": str(lowered.get("source_locator") or "").strip(),
                "evidence_quote": str(lowered.get("evidence_quote") or "").strip(),
                "evidence_note": str(lowered.get("evidence_note") or "").strip(),
                "test_environment": _activity_environment_snapshot(lowered),
                "status": RESEARCH_STATUS,
            }
            records.append(_normalize_activity(activity))
        result = self._merge_records(self.activities_path, records, "activity_id")
        return {"library_id": self.manifest.id, **result}

    def import_literature(self, source: Path) -> dict[str, Any]:
        source = source.expanduser().resolve()
        if not source.is_file():
            raise KlibError(f"Literature source is not a file: {source}")
        if source.suffix.casefold() in {".md", ".txt"}:
            text = source.read_text(encoding="utf-8-sig").strip()
            heading = next(
                (
                    line.lstrip("#").strip()
                    for line in text.splitlines()
                    if line.lstrip().startswith("#")
                ),
                source.stem,
            )
            rows = [
                {
                    "source_id": f"LIT_{re.sub(r'[^A-Za-z0-9]+', '_', source.stem).upper()}",
                    "title": heading,
                    "citation": source.name,
                    "evidence_summary": text,
                }
            ]
        else:
            rows = list(self._read_evidence_source(source))

        records = []
        for raw in rows:
            lowered = {str(key).strip().casefold(): value for key, value in raw.items()}
            title = str(lowered.get("title") or "").strip()
            summary = str(
                lowered.get("evidence_summary") or lowered.get("summary") or ""
            ).strip()
            if not title or not summary:
                raise KlibError(
                    "Literature records require title and evidence_summary"
                )
            records.append(
                {
                    "record_type": "literature",
                    "ir_version": MEDCHEM_IR_VERSION,
                    "source_id": str(
                        lowered.get("source_id") or f"LIT_{uuid.uuid4().hex[:12]}"
                    ).strip(),
                    "title": title,
                    "citation": str(lowered.get("citation") or title).strip(),
                    "url": str(lowered.get("url") or "").strip(),
                    "year": str(lowered.get("year") or "").strip(),
                    "evidence_summary": summary,
                    "status": RESEARCH_STATUS,
                }
            )
        result = self._merge_records(self.literature_path, records, "source_id")
        return {"library_id": self.manifest.id, **result}

    def targets(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.targets_path)

    def environments(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.environments_path)

    def activities(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.activities_path)

    def literature(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.literature_path)

    def evidence_status(self) -> dict[str, Any]:
        compound_ids = {
            str(item.get("compound_id", "")) for item in self.compounds(compiled=False)
        }
        target_ids = {str(item.get("target_id", "")) for item in self.targets()}
        environment_ids = {
            str(item.get("environment_id", "")) for item in self.environments()
        }
        source_ids = {str(item.get("source_id", "")) for item in self.literature()}
        activities = self.activities()
        orphan_activities = [
            item["activity_id"]
            for item in activities
            if item.get("compound_id") not in compound_ids
            or item.get("target_id") not in target_ids
        ]
        uncited_activities = [
            item["activity_id"]
            for item in activities
            if not item.get("source_ids")
            or any(source_id not in source_ids for source_id in item["source_ids"])
        ]
        missing_environments = [
            item["activity_id"]
            for item in activities
            if item.get("environment_id")
            and item.get("environment_id") not in environment_ids
        ]
        invalid_activity_records = [
            item["activity_id"]
            for item in activities
            if any(
                diagnostic.get("severity") == "error"
                for diagnostic in item.get("diagnostics", [])
            )
        ]
        compiled_for_provenance = (
            self._compiled_records() if self.compiled_path.exists() else []
        )
        missing_compound_provenance = [
            item["compound_id"]
            for item in compiled_for_provenance
            if not _compound_provenance_ready(item)
        ]
        return {
            "targets": len(target_ids),
            "test_environments": len(environment_ids),
            "bioactivity_records": len(activities),
            "literature_records": len(source_ids),
            "linked_activities": len(activities) - len(orphan_activities),
            "orphan_activities": orphan_activities,
            "uncited_activities": uncited_activities,
            "missing_environments": missing_environments,
            "invalid_activity_records": invalid_activity_records,
            "missing_compound_provenance": missing_compound_provenance,
            "ready": bool(activities)
            and not orphan_activities
            and not uncited_activities
            and not missing_environments
            and not invalid_activity_records
            and not missing_compound_provenance,
        }

    def evidence_for(self, query: str) -> dict[str, Any]:
        compound = self._resolve_compound(query)
        activities = [
            item
            for item in self.activities()
            if item.get("compound_id") == compound["compound_id"]
        ]
        target_map = {
            item["target_id"]: item for item in self.targets()
        }
        environment_map = {
            item["environment_id"]: item for item in self.environments()
        }
        literature_map = {
            item["source_id"]: item for item in self.literature()
        }
        target_ids = {item.get("target_id") for item in activities}
        source_ids = {
            source_id
            for item in activities
            for source_id in item.get("source_ids", [])
        }
        return {
            "compound": compound,
            "activities": activities,
            "targets": [
                target_map[target_id]
                for target_id in target_ids
                if target_id in target_map
            ],
            "environments": [
                environment_map[item["environment_id"]]
                for item in activities
                if item.get("environment_id") in environment_map
            ],
            "literature": [
                literature_map[source_id]
                for source_id in source_ids
                if source_id in literature_map
            ],
        }

    def research_brief(self, question: str) -> dict[str, Any]:
        gate = safety_check(question)
        if not gate["allowed"]:
            return {
                **gate,
                "answer": gate["response"],
                "compound": None,
                "activities": [],
                "targets": [],
                "environments": [],
                "citations": [],
            }

        evidence = self.evidence_for(question)
        compound = evidence["compound"]
        source_map = {
            item["source_id"]: item for item in evidence["literature"]
        }
        ordered_source_ids = []
        for activity in evidence["activities"]:
            for source_id in activity.get("source_ids", []):
                if source_id in source_map and source_id not in ordered_source_ids:
                    ordered_source_ids.append(source_id)
        citation_number = {
            source_id: index + 1
            for index, source_id in enumerate(ordered_source_ids)
        }

        statements = [
            (
                f"{compound['name']} has formula {compound['formula']}, molecular "
                f"weight {compound['molecular_weight']:.2f}, and scaffold "
                f"{compound['scaffold_smiles'] or 'acyclic'}."
            )
        ]
        target_map = {
            item["target_id"]: item for item in evidence["targets"]
        }
        environment_map = {
            item["environment_id"]: item for item in evidence["environments"]
        }
        for activity in evidence["activities"]:
            target = target_map.get(activity["target_id"], {})
            target_name = target.get("name", activity["target_id"])
            target_symbol = target.get("gene_symbol", "")
            target_label = (
                f"{target_name} ({target_symbol})" if target_symbol else target_name
            )
            measurement = " ".join(
                value
                for value in (
                    activity.get("endpoint", ""),
                    activity.get("relation", ""),
                    str(activity.get("value", "")),
                    activity.get("unit", ""),
                )
                if value
            )
            if activity.get("value_nM") is not None:
                measurement += f" ({activity['value_nM']:.3g} nM)"
            if activity.get("p_activity") is not None:
                measurement += f", pActivity {activity['p_activity']:.2f}"
            environment = environment_map.get(activity.get("environment_id"), {})
            environment_label = ""
            if environment:
                environment_label = (
                    f" in {environment.get('name', activity.get('environment_id'))}"
                    f" ({environment.get('environment_type', 'test environment')})"
                )
            elif activity.get("test_environment"):
                environment_label = " in the recorded test environment"
            claim = activity.get("result") or activity.get("evidence_note")
            references = "".join(
                f" [{citation_number[source_id]}]"
                for source_id in activity.get("source_ids", [])
                if source_id in citation_number
            )
            detail = f"; {measurement}" if measurement else ""
            statements.append(
                f"{claim} against {target_label}{environment_label}{detail}.{references}".replace(
                    "..", "."
                )
            )

        statements.append(
            "This is a research evidence summary, not a clinical recommendation. "
            "Mechanistic claims remain limited to the linked records."
        )
        citations = [
            {
                "number": citation_number[source_id],
                **source_map[source_id],
            }
            for source_id in ordered_source_ids
        ]
        return {
            "allowed": True,
            "blocked_categories": [],
            "answer": "\n\n".join(statements),
            "compound": compound,
            "activities": evidence["activities"],
            "targets": evidence["targets"],
            "environments": evidence["environments"],
            "citations": citations,
        }

    def research_agent(
        self,
        question: str,
        *,
        provider: str = "mock",
        model: str = "offline",
        base_url: str | None = None,
        api_key: str | None = None,
        pubchem_identifiers: list[str] | None = None,
        pubchem_namespace: str = "name",
        synonyms_limit: int = 12,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run a repeatable MedChem research pipeline with an optional model pass."""

        gate = safety_check(question)
        collection: dict[str, Any] = {
            "pubchem": None,
            "compiled": None,
        }
        if pubchem_identifiers:
            collection["pubchem"] = self.import_pubchem(
                pubchem_identifiers,
                namespace=pubchem_namespace,
                synonyms_limit=synonyms_limit,
            )

        if self.compounds(compiled=False):
            collection["compiled"] = self.compile()

        brief = self.research_brief(question)
        evidence_status = self.evidence_status()
        evals = self.run_evidence_evals()
        report = self.compile_report()
        context = self._research_agent_context(
            question,
            brief=brief,
            evidence_status=evidence_status,
            evals=evals,
            compile_report=report,
        )

        model_answer = None
        model_error = None
        model_safety = None
        messages = _research_agent_messages(question, context)
        if gate["allowed"]:
            try:
                model_provider = get_provider(
                    provider,
                    base_url=base_url,
                    api_key=api_key,
                )
                model_answer = model_provider.chat(
                    messages,
                    model,
                    {
                        "temperature": 0,
                        "max_tokens": 1600,
                        **(options or {}),
                    },
                )
                model_safety = safety_check(model_answer)
            except Exception as exc:  # pragma: no cover - exact provider errors vary
                model_error = str(exc)

        return {
            "created_at": utc_now(),
            "library_id": self.manifest.id,
            "question": question,
            "status": RESEARCH_STATUS,
            "provider": provider,
            "model": model,
            "collection": collection,
            "safety": gate,
            "evidence_status": evidence_status,
            "evidence_evals": evals,
            "deterministic_brief": brief,
            "context": context,
            "model_request": {
                "messages": messages,
                "options": {
                    "temperature": 0,
                    "max_tokens": 1600,
                    **(options or {}),
                },
            },
            "model_answer": model_answer,
            "model_error": model_error,
            "model_answer_safety": model_safety,
            "ready_for_review": bool(
                gate["allowed"]
                and brief.get("allowed")
                and evidence_status.get("ready")
                and evals.get("status") == "passed"
                and model_answer
                and not model_error
            ),
        }

    def _research_agent_context(
        self,
        question: str,
        *,
        brief: dict[str, Any],
        evidence_status: dict[str, Any],
        evals: dict[str, Any],
        compile_report: dict[str, Any] | None,
    ) -> dict[str, Any]:
        compound = brief.get("compound")
        compound_context = None
        if compound:
            compound_context = {
                key: compound.get(key)
                for key in (
                    "compound_id",
                    "name",
                    "synonyms",
                    "formula",
                    "molecular_weight",
                    "exact_molecular_weight",
                    "canonical_smiles",
                    "inchi",
                    "inchikey",
                    "scaffold_smiles",
                    "logp",
                    "hbd",
                    "hba",
                    "tpsa",
                    "rotatable_bonds",
                    "ring_count",
                    "source_database",
                    "source_url",
                    "source_license",
                    "external_ids",
                    "undefined_stereocenters",
                    "structural_alerts",
                    "identity_group",
                    "provenance",
                )
            }
        duplicate_groups = (
            compile_report.get("duplicate_identity_groups", [])
            if compile_report
            else []
        )
        return {
            "question": question,
            "instruction": (
                "Use only this K-LIB MedChem context. Do not invent compounds, "
                "targets, activity values, citations, clinical advice, or synthesis "
                "procedures. If evidence is missing, say what source should be "
                "imported next."
            ),
            "compound": compound_context,
            "activities": brief.get("activities", []),
            "targets": brief.get("targets", []),
            "test_environments": brief.get("environments", []),
            "citations": brief.get("citations", []),
            "deterministic_answer": brief.get("answer"),
            "evidence_status": evidence_status,
            "evidence_evals": {
                "status": evals.get("status"),
                "score": evals.get("score"),
                "passed": evals.get("passed"),
                "total": evals.get("total"),
                "checks": evals.get("checks", []),
            },
            "duplicate_identity_groups": duplicate_groups,
            "source_catalog": medchem_source_catalog(),
            "available_visualizations": {
                "skeletal_svg": bool(compound_context),
                "rdkit_3d_sdf_conformer": bool(compound_context),
            },
            "boundaries": {
                "status": RESEARCH_STATUS,
                "not_for": [
                    "clinical decisions",
                    "human dosing",
                    "synthesis procedures",
                    "harmful-compound optimization",
                ],
            },
        }

    def run_evidence_evals(self) -> dict[str, Any]:
        status = self.evidence_status()
        brief = self.research_brief("Summarize the evidence for aspirin.")
        blocked = self.research_brief(
            "Give me a step-by-step synthesis procedure for aspirin."
        )
        missing_value_provenance = _activity_value_provenance_missing(
            self.activities(),
            self.literature(),
        )
        missing_typed_ir = _typed_ir_missing(
            self.compounds(),
            self.environments(),
            self.targets(),
            self.activities(),
            self.literature(),
        )
        checks = [
            {
                "name": "Referential integrity",
                "passed": not status["orphan_activities"],
                "detail": (
                    "All activities link to known compounds and targets."
                    if not status["orphan_activities"]
                    else f"Orphans: {', '.join(status['orphan_activities'])}"
                ),
            },
            {
                "name": "Citation coverage",
                "passed": not status["uncited_activities"],
                "detail": (
                    "Every activity links to a literature record."
                    if not status["uncited_activities"]
                    else f"Uncited: {', '.join(status['uncited_activities'])}"
                ),
            },
            {
                "name": "Value provenance",
                "passed": not missing_value_provenance,
                "detail": (
                    "Activity values or claim anchors appear in cited evidence text."
                    if not missing_value_provenance
                    else f"Missing anchors: {', '.join(missing_value_provenance)}"
                ),
            },
            {
                "name": "Typed IR preview",
                "passed": not missing_typed_ir,
                "detail": (
                    f"All records declare {MEDCHEM_IR_VERSION} and record_type."
                    if not missing_typed_ir
                    else f"Missing typed IR metadata: {', '.join(missing_typed_ir)}"
                ),
            },
            {
                "name": "Test environments",
                "passed": not status["missing_environments"],
                "detail": (
                    "All activity environment links resolve."
                    if not status["missing_environments"]
                    else f"Missing environments: {', '.join(status['missing_environments'])}"
                ),
            },
            {
                "name": "Activity normalization",
                "passed": not status["invalid_activity_records"],
                "detail": (
                    "All quantitative concentration records have valid units."
                    if not status["invalid_activity_records"]
                    else f"Invalid: {', '.join(status['invalid_activity_records'])}"
                ),
            },
            {
                "name": "Compound provenance",
                "passed": not status["missing_compound_provenance"],
                "detail": (
                    "Every compiled compound keeps source refs and RDKit method labels."
                    if not status["missing_compound_provenance"]
                    else (
                        "Missing provenance: "
                        f"{', '.join(status['missing_compound_provenance'])}"
                    )
                ),
            },
            {
                "name": "Grounded research brief",
                "passed": bool(brief["citations"]) and "[" in brief["answer"],
                "detail": f"{len(brief['citations'])} cited sources returned.",
            },
            {
                "name": "Safety refusal",
                "passed": not blocked["allowed"],
                "detail": "Actionable synthesis requests are blocked.",
            },
        ]
        passed = sum(1 for check in checks if check["passed"])
        return {
            "passed": passed,
            "total": len(checks),
            "score": round((passed / len(checks)) * 100),
            "checks": checks,
            "status": "passed" if passed == len(checks) else "failed",
        }

    def similar(self, query_smiles: str, top_k: int = 10) -> list[dict[str, Any]]:
        require_rdkit()
        from rdkit import DataStructs
        from rdkit.Chem import rdFingerprintGenerator

        query = _parse_smiles(query_smiles)
        if query is None:
            raise KlibError("RDKit could not parse the query SMILES")
        generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
        query_fingerprint = generator.GetFingerprint(query)
        results = []
        for record in self._compiled_records():
            molecule = _parse_smiles(record["canonical_smiles"])
            if molecule is None:
                continue
            fingerprint = generator.GetFingerprint(molecule)
            results.append(
                {
                    "compound_id": record["compound_id"],
                    "name": record.get("name", ""),
                    "canonical_smiles": record["canonical_smiles"],
                    "inchikey": record["inchikey"],
                    "scaffold_smiles": record["scaffold_smiles"],
                    "tanimoto": round(
                        float(DataStructs.TanimotoSimilarity(query_fingerprint, fingerprint)),
                        6,
                    ),
                    "status": RESEARCH_STATUS,
                }
            )
        return sorted(
            results,
            key=lambda item: (-item["tanimoto"], item["compound_id"]),
        )[:top_k]

    def _compiled_records(self) -> list[dict[str, Any]]:
        if not self.compiled_path.exists():
            raise KlibError("Compile the MedChem package before searching it")
        return self._read_jsonl(self.compiled_path)

    def _resolve_compound(self, query: str) -> dict[str, Any]:
        needle = query.casefold()
        candidates = []
        for record in self._compiled_records():
            names = [
                str(record.get("compound_id", "")),
                str(record.get("name", "")),
                *record.get("synonyms", []),
            ]
            score = max(
                (
                    len(name)
                    for name in names
                    if name and name.casefold() in needle
                ),
                default=0,
            )
            if score:
                candidates.append((score, record))
        if not candidates:
            raise KlibError("Question must name a compiled compound")
        return max(candidates, key=lambda item: item[0])[1]

    def _read_evidence_source(self, source: Path) -> Iterable[dict[str, Any]]:
        source = source.expanduser().resolve()
        if not source.is_file():
            raise KlibError(f"Evidence source is not a file: {source}")
        if source.suffix.casefold() == ".csv":
            with source.open("r", encoding="utf-8-sig", newline="") as stream:
                yield from csv.DictReader(stream)
            return
        if source.suffix.casefold() == ".jsonl":
            yield from self._read_jsonl(source)
            return
        raise KlibError("Evidence records must use CSV or JSONL")

    def _merge_records(
        self,
        path: Path,
        records: list[dict[str, Any]],
        key: str,
    ) -> dict[str, int]:
        existing = self._read_jsonl(path)
        by_id = {str(item[key]): item for item in existing}
        imported = 0
        updated = 0
        for record in records:
            if record[key] in by_id:
                updated += 1
            else:
                imported += 1
            by_id[record[key]] = record
        self._write_jsonl(path, by_id.values())
        return {"imported": imported, "updated": updated, "total": len(by_id)}

    def _read_source(self, source: Path) -> Iterable[dict[str, Any]]:
        suffix = source.suffix.casefold()
        if suffix == ".csv":
            with source.open("r", encoding="utf-8-sig", newline="") as stream:
                yield from csv.DictReader(stream)
            return
        if suffix == ".jsonl":
            yield from self._read_jsonl(source)
            return
        if suffix in {".smi", ".txt"}:
            for line_number, line in enumerate(
                source.read_text(encoding="utf-8-sig").splitlines(), start=1
            ):
                value = line.strip()
                if not value or value.startswith("#"):
                    continue
                parts = value.split(maxsplit=1)
                yield {
                    "smiles": parts[0],
                    "name": parts[1] if len(parts) > 1 else f"Line {line_number}",
                }
            return
        if suffix == ".sdf":
            require_rdkit()
            from rdkit import Chem, rdBase

            with rdBase.BlockLogs():
                molecules = list(Chem.SDMolSupplier(str(source), removeHs=False))
            for index, molecule in enumerate(molecules, start=1):
                if molecule is None:
                    yield {"smiles": "", "name": f"Invalid SDF record {index}"}
                    continue
                properties = molecule.GetPropsAsDict()
                yield {
                    **properties,
                    "name": molecule.GetProp("_Name") if molecule.HasProp("_Name") else "",
                    "smiles": Chem.MolToSmiles(molecule),
                }

    @staticmethod
    def _normalize_record(raw: dict[str, Any], source: Path, next_number: int) -> dict[str, Any]:
        lowered = {str(key).strip().casefold(): value for key, value in raw.items()}
        compound_id = str(lowered.get("compound_id") or f"CMPD_{next_number:06d}").strip()
        smiles = str(lowered.get("smiles") or lowered.get("canonical_smiles") or "").strip()
        if not smiles:
            smiles = str(lowered.get("structure") or "").strip()
        name = str(lowered.get("name") or compound_id).strip()
        synonyms = lowered.get("synonyms") or []
        if isinstance(synonyms, str):
            synonyms = [item.strip() for item in re.split(r"[|;]", synonyms) if item.strip()]
        return {
            "compound_id": compound_id,
            "name": name,
            "smiles": smiles,
            "synonyms": list(synonyms) if isinstance(synonyms, (list, tuple)) else [],
            "known_targets": _as_list(lowered.get("known_targets")),
            "bioactivity_refs": _as_list(lowered.get("bioactivity_refs")),
            "toxicity_flags": _as_list(lowered.get("toxicity_flags")),
            "source_refs": sorted(set([*_as_list(lowered.get("source_refs")), source.name])),
            "status": RESEARCH_STATUS,
            "imported_at": utc_now(),
        }

    @staticmethod
    def _next_compound_number(records: list[dict[str, Any]]) -> int:
        numbers = []
        for record in records:
            match = re.fullmatch(r"CMPD_(\d+)", str(record.get("compound_id", "")))
            if match:
                numbers.append(int(match.group(1)))
        return max(numbers, default=0) + 1

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records = []
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8-sig").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise KlibError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise KlibError(f"JSONL record must be an object at {path}:{line_number}")
            records.append(value)
        return records

    @staticmethod
    def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records
            ),
            encoding="utf-8",
        )


def describe_molecule(smiles: str) -> dict[str, Any]:
    require_rdkit()
    from rdkit import Chem, rdBase
    from rdkit.Chem import Crippen, Descriptors, Lipinski, rdFingerprintGenerator, rdMolDescriptors
    from rdkit.Chem.Scaffolds import MurckoScaffold

    molecule = standardize_molecule(smiles)
    if molecule is None:
        raise KlibError("RDKit could not parse the SMILES")
    with rdBase.BlockLogs():
        canonical_smiles = Chem.MolToSmiles(molecule, canonical=True)
        generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
        fingerprint = generator.GetFingerprint(molecule)
        undefined_stereo = [
            f"{atom_index}:{label}"
            for atom_index, label in Chem.FindMolChiralCenters(
                molecule,
                includeUnassigned=True,
                useLegacyImplementation=False,
            )
            if label == "?"
        ]
        inchi = Chem.MolToInchi(molecule)
        inchikey = Chem.MolToInchiKey(molecule)
        formula = rdMolDescriptors.CalcMolFormula(molecule)
        molecular_weight = round(float(Descriptors.MolWt(molecule)), 6)
        exact_molecular_weight = round(float(Descriptors.ExactMolWt(molecule)), 6)
        logp = round(float(Crippen.MolLogP(molecule)), 6)
        hbd = int(Lipinski.NumHDonors(molecule))
        hba = int(Lipinski.NumHAcceptors(molecule))
        tpsa = round(float(rdMolDescriptors.CalcTPSA(molecule)), 6)
        rotatable_bonds = int(rdMolDescriptors.CalcNumRotatableBonds(molecule))
        ring_count = int(rdMolDescriptors.CalcNumRings(molecule))
        fraction_csp3 = round(float(rdMolDescriptors.CalcFractionCSP3(molecule)), 6)
        scaffold_smiles = MurckoScaffold.MurckoScaffoldSmiles(mol=molecule)
        structural_alerts = structural_alerts_for_molecule(molecule)
    return {
        "record_type": "compound",
        "ir_version": MEDCHEM_IR_VERSION,
        "canonical_smiles": canonical_smiles,
        "inchi": inchi,
        "inchikey": inchikey,
        "formula": formula,
        "molecular_weight": molecular_weight,
        "exact_molecular_weight": exact_molecular_weight,
        "logp": logp,
        "hbd": hbd,
        "hba": hba,
        "tpsa": tpsa,
        "rotatable_bonds": rotatable_bonds,
        "ring_count": ring_count,
        "heavy_atom_count": int(molecule.GetNumHeavyAtoms()),
        "formal_charge": int(sum(atom.GetFormalCharge() for atom in molecule.GetAtoms())),
        "fraction_csp3": fraction_csp3,
        "scaffold_smiles": scaffold_smiles,
        "undefined_stereocenters": undefined_stereo,
        "structural_alerts": structural_alerts,
        "descriptor_methods": dict(DESCRIPTOR_METHODS),
        "morgan_radius": 2,
        "morgan_bits": 2048,
        "fingerprint_on_bits": list(fingerprint.GetOnBits()),
        "status": RESEARCH_STATUS,
    }


def medchem_source_catalog() -> dict[str, dict[str, str]]:
    return {key: dict(value) for key, value in MEDCHEM_SOURCE_CATALOG.items()}


def _research_agent_messages(
    question: str,
    context: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a cautious medicinal-chemistry research assistant. "
                "Use only the supplied K-LIB MedChem JSON context. Never invent "
                "compounds, targets, activity values, or citations. Do not provide "
                "synthesis procedures, human dosing advice, clinical decisions, or "
                "harmful-compound optimization. Return a concise research report with "
                "sections: identity, descriptors, evidence, citations, duplicate "
                "identity notes, uncertainty, and next data to import."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Research question:\n{question}\n\n"
                "K-LIB MedChem context JSON:\n"
                f"{json.dumps(context, ensure_ascii=False, indent=2)}"
            ),
        },
    ]


def conformer_3d_sdf(smiles: str, *, random_seed: int = 61453) -> str:
    require_rdkit()
    from rdkit import Chem, rdBase
    from rdkit.Chem import AllChem

    with rdBase.BlockLogs():
        molecule = standardize_molecule(smiles)
        if molecule is None:
            raise KlibError("RDKit could not parse the SMILES")
        molecule = Chem.AddHs(molecule)
        params = AllChem.ETKDGv3()
        params.randomSeed = random_seed
        params.useRandomCoords = True
        status = AllChem.EmbedMolecule(molecule, params)
        if status != 0:
            raise KlibError("RDKit could not generate a 3D conformer")
        AllChem.UFFOptimizeMolecule(molecule, maxIters=200)
        molecule.SetProp("_Name", "K-LIB Forge 3D conformer")
        molecule.SetProp("generation_method", "RDKit ETKDGv3 + UFF")
        molecule.SetProp("source_smiles", smiles)
        molecule.SetProp("status", RESEARCH_STATUS)
        output = io.StringIO()
        writer = Chem.SDWriter(output)
        writer.write(molecule)
        writer.close()
        return output.getvalue()


def fetch_pubchem_compound(
    identifier: str,
    *,
    namespace: str = "name",
    synonyms_limit: int = 12,
) -> dict[str, Any]:
    if namespace not in {"name", "cid"}:
        raise KlibError("PubChem namespace must be 'name' or 'cid'")
    identifier = identifier.strip()
    if not identifier:
        raise KlibError("PubChem identifier cannot be empty")

    encoded = urllib.parse.quote(identifier, safe="")
    properties = ",".join(
        [
            "Title",
            "CanonicalSMILES",
            "IsomericSMILES",
            "IUPACName",
            "MolecularFormula",
            "MolecularWeight",
            "InChI",
            "InChIKey",
        ]
    )
    property_url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
        f"{namespace}/{encoded}/property/{properties}/JSON"
    )
    payload = _fetch_json(property_url)
    rows = payload.get("PropertyTable", {}).get("Properties", [])
    if not rows:
        raise KlibError(f"PubChem returned no compound properties for {identifier!r}")
    row = rows[0]
    cid = str(row.get("CID") or "").strip()
    if not cid:
        raise KlibError(f"PubChem response for {identifier!r} did not include a CID")

    synonyms = _pubchem_synonyms(cid, limit=synonyms_limit)
    title = str(row.get("Title") or identifier).strip()
    smiles = str(
        row.get("IsomericSMILES")
        or row.get("CanonicalSMILES")
        or row.get("SMILES")
        or row.get("ConnectivitySMILES")
        or ""
    ).strip()
    if not smiles:
        raise KlibError(f"PubChem CID {cid} did not include a SMILES structure")

    source_url = f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"
    return {
        "compound_id": f"PUBCHEM_CID_{cid}",
        "name": title,
        "smiles": smiles,
        "synonyms": synonyms,
        "known_targets": [],
        "bioactivity_refs": [],
        "toxicity_flags": [],
        "source_refs": [f"PubChem CID:{cid}"],
        "external_ids": {"pubchem_cid": cid},
        "source_database": "PubChem",
        "source_url": source_url,
        "source_license": MEDCHEM_SOURCE_CATALOG["pubchem"]["license"],
        "source_accessed_at": utc_now(),
        "status": RESEARCH_STATUS,
        "imported_at": utc_now(),
        "pubchem": {
            "cid": cid,
            "title": title,
            "canonical_smiles": str(
                row.get("CanonicalSMILES")
                or row.get("ConnectivitySMILES")
                or row.get("SMILES")
                or ""
            ).strip(),
            "isomeric_smiles": str(
                row.get("IsomericSMILES") or row.get("SMILES") or ""
            ).strip(),
            "iupac_name": str(row.get("IUPACName") or "").strip(),
            "molecular_formula": str(row.get("MolecularFormula") or "").strip(),
            "molecular_weight": row.get("MolecularWeight"),
            "inchi": str(row.get("InChI") or "").strip(),
            "inchikey": str(row.get("InChIKey") or "").strip(),
        },
    }


def _pubchem_synonyms(cid: str, *, limit: int) -> list[str]:
    if limit <= 0:
        return []
    synonyms_url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
        f"cid/{urllib.parse.quote(cid, safe='')}/synonyms/JSON"
    )
    try:
        payload = _fetch_json(synonyms_url)
    except KlibError:
        return []
    rows = payload.get("InformationList", {}).get("Information", [])
    synonyms = rows[0].get("Synonym", []) if rows else []
    return [str(item).strip() for item in synonyms if str(item).strip()][:limit]


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "K-LIB Forge MedChem Lab/0.1"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise KlibError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise KlibError(f"Could not reach {url}: {exc.reason}") from exc
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise KlibError(f"Invalid JSON from {url}: {exc}") from exc
    if not isinstance(value, dict):
        raise KlibError(f"Expected JSON object from {url}")
    return value


def skeletal_svg(
    smiles: str,
    *,
    width: int = 280,
    height: int = 170,
) -> str:
    require_rdkit()
    from rdkit import rdBase
    from rdkit.Chem.Draw import rdMolDraw2D

    with rdBase.BlockLogs():
        molecule = standardize_molecule(smiles)
        if molecule is None:
            raise KlibError("RDKit could not parse the SMILES")

        drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
        options = drawer.drawOptions()
        options.clearBackground = False
        options.padding = 0.08
        options.bondLineWidth = 1.8
        rdMolDraw2D.PrepareAndDrawMolecule(drawer, molecule)
        drawer.FinishDrawing()
        return drawer.GetDrawingText().replace("svg:", "")


def standardize_molecule(smiles: str) -> Any:
    molecule = _parse_smiles(smiles)
    if molecule is None:
        return None
    require_rdkit()
    from rdkit.Chem.MolStandardize import rdMolStandardize

    chooser = rdMolStandardize.LargestFragmentChooser()
    normalizer = rdMolStandardize.Normalizer()
    uncharger = rdMolStandardize.Uncharger()
    tautomer = rdMolStandardize.TautomerEnumerator()
    molecule = chooser.choose(molecule)
    molecule = normalizer.normalize(molecule)
    molecule = uncharger.uncharge(molecule)
    return tautomer.Canonicalize(molecule)


def structural_alerts_for_molecule(molecule: Any) -> list[dict[str, str]]:
    require_rdkit()

    catalog = _structural_alert_catalog()
    alerts = []
    for entry in catalog.GetMatches(molecule):
        filter_set = _entry_prop(entry, "FilterSet")
        alerts.append(
            {
                "name": entry.GetDescription(),
                "filter_set": filter_set,
                "scope": _entry_prop(entry, "Scope"),
                "reference": _entry_prop(entry, "Reference"),
            }
        )
    return sorted(alerts, key=lambda item: (item["filter_set"], item["name"]))


def _compound_provenance(
    record: dict[str, Any],
    result: dict[str, Any],
    *,
    compiled_at: str,
    standardized: bool,
) -> dict[str, Any]:
    return {
        "compound_id": str(record.get("compound_id", "")),
        "source_refs": _as_list(record.get("source_refs")),
        "original_smiles": str(record.get("smiles", "")),
        "canonical_smiles": str(result.get("canonical_smiles", "")),
        "inchikey": str(result.get("inchikey", "")),
        "imported_at": str(record.get("imported_at", "")),
        "compiled_at": compiled_at,
        "standardized": standardized,
        "standardization_method": DESCRIPTOR_METHODS["standardization"],
        "identity_method": DESCRIPTOR_METHODS["identity"],
        "descriptor_methods": dict(DESCRIPTOR_METHODS),
        "status": RESEARCH_STATUS,
    }


def _compound_provenance_ready(record: dict[str, Any]) -> bool:
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        return False
    required_text = (
        "compound_id",
        "original_smiles",
        "canonical_smiles",
        "inchikey",
        "compiled_at",
        "standardization_method",
        "identity_method",
    )
    return (
        all(str(provenance.get(field, "")).strip() for field in required_text)
        and bool(provenance.get("source_refs"))
        and isinstance(provenance.get("descriptor_methods"), dict)
    )


def _activity_value_provenance_missing(
    activities: list[dict[str, Any]],
    literature: list[dict[str, Any]],
) -> list[str]:
    source_text = {
        item["source_id"]: _normalize_anchor_text(
            " ".join(
                str(item.get(field, ""))
                for field in ("title", "citation", "evidence_summary")
            )
        )
        for item in literature
    }
    missing = []
    for activity in activities:
        cited = " ".join(
            source_text[source_id]
            for source_id in activity.get("source_ids", [])
            if source_id in source_text
        )
        if not cited:
            continue
        anchors = _activity_value_anchors(activity)
        quote = str(activity.get("evidence_quote") or "").strip()
        if quote:
            anchors.append(quote)
        if not anchors:
            anchors = _claim_anchors(str(activity.get("result") or ""))
        if anchors and not any(_normalize_anchor_text(anchor) in cited for anchor in anchors):
            missing.append(str(activity["activity_id"]))
    return missing


def _typed_ir_missing(
    compounds: list[dict[str, Any]],
    environments: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    literature: list[dict[str, Any]],
) -> list[str]:
    groups = (
        ("compound", compounds, "compound_id"),
        ("test_environment", environments, "environment_id"),
        ("target", targets, "target_id"),
        ("activity", activities, "activity_id"),
        ("literature", literature, "source_id"),
    )
    missing = []
    for expected_type, records, key in groups:
        for record in records:
            if (
                record.get("record_type") != expected_type
                or record.get("ir_version") != MEDCHEM_IR_VERSION
            ):
                missing.append(str(record.get(key, "<unknown>")))
    return missing


def _activity_value_anchors(activity: dict[str, Any]) -> list[str]:
    anchors = []
    value = str(activity.get("value") or "").strip()
    unit = str(activity.get("unit") or "").strip()
    if value:
        anchors.append(value)
    if unit:
        concentration = re.search(r"(\d+(?:\.\d+)?)\s*(?:uM|µM|μM|nM|mM|pM|M)\b", unit)
        if concentration:
            anchors.append(concentration.group(0))
    if activity.get("value_nM") is not None:
        anchors.append(f"{activity['value_nM']:.3g} nM")
    return anchors


def _claim_anchors(result: str) -> list[str]:
    words = [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z0-9-]{5,}", result)
        if word.casefold()
        not in {"through", "primarily", "tracked", "context", "dependent"}
    ]
    return words[:4]


def _normalize_anchor_text(value: str) -> str:
    return (
        value.casefold()
        .replace("µ", "u")
        .replace("μ", "u")
        .replace("-", " ")
    )


@lru_cache(maxsize=1)
def _structural_alert_catalog() -> Any:
    from rdkit.Chem import FilterCatalog

    params = FilterCatalog.FilterCatalogParams()
    catalogs = FilterCatalog.FilterCatalogParams.FilterCatalogs
    for name in ("PAINS_A", "PAINS_B", "PAINS_C", "BRENK", "NIH"):
        params.AddCatalog(getattr(catalogs, name))
    return FilterCatalog.FilterCatalog(params)


def _entry_prop(entry: Any, name: str) -> str:
    return entry.GetProp(name) if name in entry.GetPropList() else ""


def identity_for_molecule(molecule: Any) -> dict[str, str]:
    require_rdkit()
    from rdkit import Chem

    return {
        "canonical_smiles": Chem.MolToSmiles(molecule, canonical=True),
        "inchi": Chem.MolToInchi(molecule),
        "inchikey": Chem.MolToInchiKey(molecule),
    }


def scaffold_for_smiles(smiles: str) -> dict[str, str]:
    description = describe_molecule(smiles)
    return {
        "canonical_smiles": description["canonical_smiles"],
        "scaffold_smiles": description["scaffold_smiles"],
        "status": RESEARCH_STATUS,
    }


def safety_check(request: str) -> dict[str, Any]:
    text = request.casefold()
    categories = []
    patterns = {
        "synthesis_instructions": (
            r"\b(step[- ]by[- ]step|recipe|procedure|reaction conditions?)\b.*"
            r"\b(synthesi[sz]e|synthesis|make|manufacture|compound)\b|"
            r"\b(synthesi[sz]e|manufacture)\b.*\bcompound\b"
        ),
        "human_dosage_advice": (
            r"\b(recommend|calculate|prescribe|tell me)\b.*"
            r"\b(human|patient|dose|dosage|mg/kg|administration)\b|"
            r"\bwhat dose\b"
        ),
        "controlled_substance_optimization": (
            r"\b(optimi[sz]e|increase|improve|design)\b.*"
            r"\b(controlled substance|recreational|euphoria|addictive potency)\b"
        ),
        "toxin_or_poison_optimization": (
            r"\b(optimi[sz]e|increase|improve|design|make)\b.*"
            r"\b(toxin|poison|lethality|lethal|fatal)\b"
        ),
        "pathogen_or_biohazard_optimization": (
            r"\b(optimi[sz]e|increase|improve|design|engineer)\b.*"
            r"\b(pathogen|biohazard|virulence|infectivity)\b"
        ),
    }
    for category, pattern in patterns.items():
        if re.search(pattern, text):
            categories.append(category)
    return {
        "allowed": not categories,
        "blocked_categories": categories,
        "response": REFUSAL
        if categories
        else (
            "Allowed research-only request. Keep claims evidence-grounded and "
            "do not infer clinical efficacy."
        ),
    }


def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[|;]", str(value)) if item.strip()]


def _activity_environment_snapshot(lowered: dict[str, Any]) -> dict[str, str]:
    fields = {
        "temperature_c": lowered.get("temperature_c"),
        "ph": lowered.get("ph") or lowered.get("pH"),
        "solvent": lowered.get("solvent"),
        "buffer": lowered.get("buffer"),
        "cell_line": lowered.get("cell_line"),
        "organism": lowered.get("organism"),
        "assay_format": lowered.get("assay_format"),
        "instrument": lowered.get("instrument"),
    }
    return {
        key: str(value).strip()
        for key, value in fields.items()
        if value is not None and str(value).strip()
    }


def _normalize_activity(activity: dict[str, Any]) -> dict[str, Any]:
    value = _parse_number(activity.get("value"))
    unit = str(activity.get("unit") or "").strip()
    normalized_unit = _normalize_unit(unit)
    endpoint = str(activity.get("endpoint") or "").casefold()
    requires_concentration = any(token in endpoint for token in PACTIVITY_ENDPOINTS)
    diagnostics = list(activity.get("diagnostics", []))
    normalized = {
        **activity,
        "value_number": value,
        "value_nM": None,
        "p_activity": None,
        "normalized_unit": "",
        "normalization_method": "",
        "diagnostics": diagnostics,
    }
    if value is None:
        if requires_concentration:
            diagnostics.append(
                _diagnostic(
                    "error",
                    "CHEM-E051",
                    str(activity["activity_id"]),
                    "value",
                    "Quantitative concentration endpoint is missing a numeric value.",
                )
            )
        return normalized

    if not unit:
        if requires_concentration:
            diagnostics.append(
                _diagnostic(
                    "error",
                    "CHEM-E050",
                    str(activity["activity_id"]),
                    "unit",
                    "Quantitative concentration endpoint is missing a unit.",
                )
            )
        return normalized

    if normalized_unit not in CONCENTRATION_UNITS:
        if requires_concentration:
            diagnostics.append(
                _diagnostic(
                    "error",
                    "CHEM-E052",
                    str(activity["activity_id"]),
                    "unit",
                    f"Unsupported concentration unit: {unit}",
                )
            )
        return normalized

    molar = value * CONCENTRATION_UNITS[normalized_unit]
    normalized["value_nM"] = round(molar * 1e9, 6)
    normalized["normalized_unit"] = "nM"
    normalized["normalization_method"] = "molar_to_nM"
    if requires_concentration and molar > 0:
        import math

        normalized["p_activity"] = round(-math.log10(molar), 2)
    return normalized


def _parse_number(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_unit(unit: str) -> str:
    return (
        unit.strip()
        .replace("μ", "µ")
        .casefold()
        .replace(" ", "")
        .replace("micro", "µ")
    )


def _canonical_smiles(smiles: str) -> str:
    molecule = _parse_smiles(smiles)
    if molecule is None:
        return ""
    from rdkit import Chem

    return Chem.MolToSmiles(molecule, canonical=True)


def _diagnostic(
    severity: str,
    code: str,
    record_id: str,
    field: str,
    message: str,
) -> dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "record_id": record_id,
        "field": field,
        "message": message,
    }


def _parse_smiles(smiles: str) -> Any:
    if not smiles:
        return None
    require_rdkit()
    from rdkit import Chem, rdBase

    with rdBase.BlockLogs():
        return Chem.MolFromSmiles(smiles)
