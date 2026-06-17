from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("rdkit")

from klib_core.examples import install_builtin_example
from klib_core.library import LibraryManager
from klib_core.medchem import (
    MEDCHEM_LITE_DESCRIPTION,
    MedChemStore,
    conformer_3d_sdf,
    describe_molecule,
    initialize_medchem_library,
    medchem_source_catalog,
    safety_check,
    scaffold_for_smiles,
    skeletal_svg,
    standardize_molecule,
)

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"


@pytest.fixture
def medchem_store(tmp_path: Path) -> MedChemStore:
    manager = LibraryManager(tmp_path / "home")
    _, library_path = initialize_medchem_library(
        manager,
        "MedChem Test",
        library_id="medchem-test",
        path=tmp_path / "medchem-test",
    )
    assert (library_path / "policies" / "medchem_safety_policy.json").exists()
    return MedChemStore(manager, "medchem-test")


def test_descriptors_and_scaffold_are_rdkit_derived() -> None:
    result = describe_molecule(ASPIRIN)
    assert result["record_type"] == "compound"
    assert result["ir_version"] == "medchem-ir-preview.1"
    assert result["canonical_smiles"] == ASPIRIN
    assert result["formula"] == "C9H8O4"
    assert result["molecular_weight"] == pytest.approx(180.159, abs=0.001)
    assert result["hbd"] == 1
    assert result["hba"] == 3
    assert result["scaffold_smiles"] == "c1ccccc1"
    assert result["descriptor_methods"]["logp"] == "RDKit Crippen.MolLogP (cLogP)"
    assert result["fingerprint_on_bits"]
    assert scaffold_for_smiles(ASPIRIN)["scaffold_smiles"] == "c1ccccc1"
    drawing = skeletal_svg(ASPIRIN, width=240, height=140)
    assert "<svg" in drawing
    assert "width='240px'" in drawing
    assert "height='140px'" in drawing
    sdf = conformer_3d_sdf(ASPIRIN)
    assert "K-LIB Forge 3D conformer" in sdf
    assert "$$$$" in sdf
    assert "generation_method" in sdf


def test_standardization_collapses_salts_and_solvents() -> None:
    from rdkit import Chem

    variants = [
        ASPIRIN,
        "CC(=O)Oc1ccccc1C(=O)[O-].[Na+]",
        "CC(=O)Oc1ccccc1C(=O)O.O",
    ]
    keys = {
        Chem.MolToInchiKey(standardize_molecule(smiles))
        for smiles in variants
    }
    assert keys == {"BSYNRYMUTXBXSQ-UHFFFAOYSA-N"}


def test_import_validate_compile_search_and_similarity(
    medchem_store: MedChemStore, tmp_path: Path
) -> None:
    source = tmp_path / "compounds.csv"
    source.write_text(
        "compound_id,name,smiles,synonyms\n"
        f"CMPD_000001,Aspirin,{ASPIRIN},acetylsalicylic acid\n"
        "CMPD_000002,Salicylic acid,O=C(O)c1ccccc1O,2-hydroxybenzoic acid\n"
        "CMPD_000003,Caffeine,Cn1c(=O)c2c(ncn2C)n(C)c1=O,\n"
        "CMPD_000004,Broken,C1(CC,invalid\n",
        encoding="utf-8",
    )

    imported = medchem_store.import_compounds(source)
    assert imported["imported"] == 4
    assert imported["total"] == 4

    validation = medchem_store.validate()
    assert validation["valid"] == 3
    assert validation["invalid"] == 1

    report = medchem_store.compile()
    assert report["knowledge_ir_version"] == "medchem-ir-preview.1"
    assert report["validator_profile"] == "rdkit-medchem-preview"
    assert report["valid_compounds"] == 3
    assert report["invalid_compounds"] == 1
    assert report["unique_scaffolds"] >= 2
    assert any(item["code"] == "CHEM-E001" for item in report["diagnostics"])

    search = medchem_store.search("acetylsalicylic")
    assert [item["name"] for item in search] == ["Aspirin"]

    similar = medchem_store.similar(ASPIRIN, top_k=3)
    assert similar[0]["name"] == "Aspirin"
    assert similar[0]["tanimoto"] == 1.0
    assert similar[1]["name"] == "Salicylic acid"

    compiled = [
        json.loads(line)
        for line in medchem_store.compiled_path.read_text(encoding="utf-8").splitlines()
    ]
    assert all(item["status"] == "research_reference_only" for item in compiled)
    assert all(item["provenance"]["source_refs"] for item in compiled)
    assert all(
        item["provenance"]["descriptor_methods"]["logp"]
        == "RDKit Crippen.MolLogP (cLogP)"
        for item in compiled
    )


def test_pubchem_import_preserves_database_provenance(
    medchem_store: MedChemStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fetch(identifier: str, *, namespace: str, synonyms_limit: int) -> dict:
        assert identifier == "aspirin"
        assert namespace == "name"
        assert synonyms_limit == 3
        return {
            "compound_id": "PUBCHEM_CID_2244",
            "name": "Aspirin",
            "smiles": ASPIRIN,
            "synonyms": ["Aspirin", "Acetylsalicylic acid"],
            "known_targets": [],
            "bioactivity_refs": [],
            "toxicity_flags": [],
            "source_refs": ["PubChem CID:2244"],
            "external_ids": {"pubchem_cid": "2244"},
            "source_database": "PubChem",
            "source_url": "https://pubchem.ncbi.nlm.nih.gov/compound/2244",
            "source_license": "public-domain/us-government-open-data",
            "status": "research_reference_only",
            "imported_at": "2026-06-16T00:00:00+00:00",
        }

    monkeypatch.setattr("klib_core.medchem.fetch_pubchem_compound", fake_fetch)

    result = medchem_store.import_pubchem(["aspirin"], synonyms_limit=3)
    assert result["provider"] == "pubchem"
    assert result["imported"] == 1
    assert result["failed"] == 0

    raw = medchem_store.compounds(compiled=False)[0]
    assert raw["compound_id"] == "PUBCHEM_CID_2244"
    assert raw["external_ids"]["pubchem_cid"] == "2244"
    assert raw["source_database"] == "PubChem"
    assert raw["source_refs"] == ["PubChem CID:2244"]

    report = medchem_store.compile()
    assert report["valid_compounds"] == 1
    compiled = medchem_store.compounds()[0]
    assert compiled["provenance"]["source_refs"] == ["PubChem CID:2244"]


def test_source_catalog_flags_cas_as_noncommercial() -> None:
    catalog = medchem_source_catalog()
    assert catalog["pubchem"]["status"] == "active"
    assert catalog["cas_common_chemistry"]["license"] == "CC BY-NC 4.0"
    assert catalog["cas_common_chemistry"]["commercial_use"] == (
        "not allowed without separate commercial license"
    )


def test_compile_reports_standardized_duplicate_identity(
    medchem_store: MedChemStore,
    tmp_path: Path,
) -> None:
    source = tmp_path / "compounds.csv"
    source.write_text(
        "compound_id,name,smiles\n"
        f"CMPD_000001,Aspirin,{ASPIRIN}\n"
        "CMPD_000002,Aspirin sodium,CC(=O)Oc1ccccc1C(=O)[O-].[Na+]\n",
        encoding="utf-8",
    )
    medchem_store.import_compounds(source)
    report = medchem_store.compile()
    assert report["duplicate_inchikeys"] == ["BSYNRYMUTXBXSQ-UHFFFAOYSA-N"]
    assert report["duplicate_identity_groups"][0]["inchikey"] == (
        "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    )
    assert report["duplicate_identity_groups"][0]["compound_ids"] == [
        "CMPD_000001",
        "CMPD_000002",
    ]
    assert report["duplicate_identity_groups"][0]["primary_compound_id"] == (
        "CMPD_000001"
    )
    assert report["duplicate_identity_groups"][0]["resolution"] == "linked_for_review"
    assert "recommended_action" in report["duplicate_identity_groups"][0]
    compiled = {item["compound_id"]: item for item in medchem_store.compounds()}
    assert compiled["CMPD_000002"]["identity_group"]["primary_compound_id"] == (
        "CMPD_000001"
    )
    codes = {item["code"] for item in report["diagnostics"]}
    assert {"CHEM-W010", "CHEM-W011"} <= codes


def test_compile_reports_stereo_and_structural_alert_diagnostics(
    medchem_store: MedChemStore,
    tmp_path: Path,
) -> None:
    source = tmp_path / "compounds.csv"
    source.write_text(
        "compound_id,name,smiles\n"
        "CMPD_STEREO,Ibuprofen,CC(C)Cc1ccc(cc1)C(C)C(=O)O\n"
        "CMPD_ALERT,Catechol,Oc1ccccc1O\n",
        encoding="utf-8",
    )
    medchem_store.import_compounds(source)
    report = medchem_store.compile()

    by_id = {
        item["compound_id"]: item
        for item in medchem_store.compounds()
    }
    assert by_id["CMPD_STEREO"]["undefined_stereocenters"] == ["10:?"]
    assert by_id["CMPD_ALERT"]["structural_alerts"]
    codes_by_record = {
        (item["record_id"], item["code"])
        for item in report["diagnostics"]
    }
    assert ("CMPD_STEREO", "CHEM-W020") in codes_by_record
    assert ("CMPD_ALERT", "CHEM-W040") in codes_by_record


def test_linked_evidence_research_brief_and_evals(
    medchem_store: MedChemStore,
    tmp_path: Path,
) -> None:
    compounds = tmp_path / "compounds.csv"
    compounds.write_text(
        "compound_id,name,smiles\n"
        f"CMPD_000001,Aspirin,{ASPIRIN}\n",
        encoding="utf-8",
    )
    medchem_store.import_compounds(compounds)
    medchem_store.compile()

    targets = tmp_path / "targets.csv"
    targets.write_text(
        "target_id,name,gene_symbol,organism\n"
        "TGT_PTGS1,Cyclooxygenase-1,PTGS1,Homo sapiens\n",
        encoding="utf-8",
    )
    environments = tmp_path / "environments.csv"
    environments.write_text(
        "environment_id,name,environment_type,lab_name,temperature_c,ph,assay_platform\n"
        "ENV_LAB_001,Teaching enzyme assay,in_vitro,K-LIB teaching lab,37,7.4,"
        "plate reader\n",
        encoding="utf-8",
    )
    literature = tmp_path / "literature.jsonl"
    literature.write_text(
        json.dumps(
            {
                "source_id": "LIT_001",
                "title": "Aspirin mechanism paper",
                "citation": "Example citation",
                "url": "https://example.test/paper",
                "evidence_summary": "Aspirin acetylation tracked with enzyme inhibition.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    activities = tmp_path / "activities.jsonl"
    activities.write_text(
        json.dumps(
            {
                "activity_id": "ACT_001",
                "compound_id": "CMPD_000001",
                "target_id": "TGT_PTGS1",
                "environment_id": "ENV_LAB_001",
                "assay_type": "biochemical",
                "endpoint": "inhibition",
                "result": "Aspirin inhibited cyclooxygenase activity",
                "source_ids": ["LIT_001"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    medchem_store.import_targets(targets)
    medchem_store.import_environments(environments)
    medchem_store.import_literature(literature)
    medchem_store.import_bioactivity(activities)

    status = medchem_store.evidence_status()
    assert status["ready"]
    assert status["test_environments"] == 1
    assert status["linked_activities"] == 1
    assert status["missing_compound_provenance"] == []

    brief = medchem_store.research_brief("Summarize evidence for aspirin")
    assert brief["allowed"]
    assert "Cyclooxygenase-1" in brief["answer"]
    assert "Teaching enzyme assay" in brief["answer"]
    assert "[1]" in brief["answer"]
    assert brief["environments"][0]["environment_id"] == "ENV_LAB_001"
    assert brief["citations"][0]["source_id"] == "LIT_001"

    evals = medchem_store.run_evidence_evals()
    assert evals["status"] == "passed"
    assert evals["score"] == 100
    assert any(check["name"] == "Compound provenance" for check in evals["checks"])
    assert any(check["name"] == "Value provenance" for check in evals["checks"])
    assert any(check["name"] == "Typed IR preview" for check in evals["checks"])


def test_activity_normalization_and_unit_diagnostics(
    medchem_store: MedChemStore,
    tmp_path: Path,
) -> None:
    compounds = tmp_path / "compounds.csv"
    compounds.write_text(
        "compound_id,name,smiles\n"
        f"CMPD_000001,Aspirin,{ASPIRIN}\n",
        encoding="utf-8",
    )
    medchem_store.import_compounds(compounds)
    medchem_store.compile()
    targets = tmp_path / "targets.csv"
    targets.write_text(
        "target_id,name,gene_symbol,organism\n"
        "TGT_PTGS1,Cyclooxygenase-1,PTGS1,Homo sapiens\n",
        encoding="utf-8",
    )
    literature = tmp_path / "literature.jsonl"
    literature.write_text(
        json.dumps(
            {
                "source_id": "LIT_001",
                "title": "Assay source",
                "citation": "Example citation",
                "evidence_summary": "Aspirin IC50 was reported as 100 uM.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    activities = tmp_path / "activities.jsonl"
    activities.write_text(
        json.dumps(
            {
                "activity_id": "ACT_GOOD",
                "compound_id": "CMPD_000001",
                "target_id": "TGT_PTGS1",
                "endpoint": "IC50",
                "relation": "=",
                "value": "100",
                "unit": "uM",
                "result": "Aspirin inhibited cyclooxygenase activity",
                "source_ids": ["LIT_001"],
            }
        )
        + "\n"
        + json.dumps(
            {
                "activity_id": "ACT_BAD",
                "compound_id": "CMPD_000001",
                "target_id": "TGT_PTGS1",
                "endpoint": "IC50",
                "value": "10",
                "result": "Missing-unit control",
                "source_ids": ["LIT_001"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    medchem_store.import_targets(targets)
    medchem_store.import_literature(literature)
    medchem_store.import_bioactivity(activities)

    by_id = {item["activity_id"]: item for item in medchem_store.activities()}
    assert by_id["ACT_GOOD"]["value_nM"] == 100000.0
    assert by_id["ACT_GOOD"]["p_activity"] == 4.0
    assert by_id["ACT_BAD"]["diagnostics"][0]["code"] == "CHEM-E050"
    status = medchem_store.evidence_status()
    assert not status["ready"]
    assert status["invalid_activity_records"] == ["ACT_BAD"]


def test_safety_gate_blocks_actionable_requests_but_allows_analysis() -> None:
    synthesis = safety_check(
        "Give me a step-by-step synthesis procedure to manufacture this compound."
    )
    assert not synthesis["allowed"]
    assert "synthesis_instructions" in synthesis["blocked_categories"]

    dosing = safety_check("What dose should I prescribe to a human patient?")
    assert not dosing["allowed"]
    assert "human_dosage_advice" in dosing["blocked_categories"]

    allowed = safety_check(
        "Compare aspirin and salicylic acid scaffolds and summarize known evidence."
    )
    assert allowed["allowed"]
    assert allowed["blocked_categories"] == []


def test_builtin_medchem_example_installs_compiled_records(tmp_path: Path) -> None:
    manager = LibraryManager(tmp_path / "home")
    created, path = install_builtin_example(manager, "medchem-lite")
    assert created
    assert path.exists()

    store = MedChemStore(manager, "medchem-lite")
    assert store.manifest.description == MEDCHEM_LITE_DESCRIPTION
    assert store.manifest.model_extra["knowledge_ir_version"] == "medchem-ir-preview.1"
    assert store.manifest.model_extra["validator_profile"]["id"] == "rdkit-medchem-preview"
    validation = store.validate()
    assert validation["valid"] == 5
    assert validation["invalid"] == 1
    report = store.compile_report()
    assert report
    assert any(item["code"] == "CHEM-W020" for item in report["diagnostics"])
    assert any(item["code"] == "CHEM-W040" for item in report["diagnostics"])
    assert store.search("aspirin")[0]["name"] == "Aspirin"
    evidence = store.evidence_status()
    assert evidence["targets"] == 3
    assert evidence["test_environments"] == 2
    assert evidence["bioactivity_records"] == 5
    assert evidence["literature_records"] == 4
    assert evidence["ready"]
    assert evidence["missing_compound_provenance"] == []
    evals = store.run_evidence_evals()
    assert evals["score"] == 100
    assert evals["total"] == 9

    agent = store.research_agent(
        "Summarize evidence for aspirin and identify next data to import.",
        provider="mock",
        model="offline",
    )
    assert agent["ready_for_review"]
    assert agent["provider"] == "mock"
    assert agent["model_answer"]
    assert agent["context"]["compound"]["name"] == "Aspirin"
    assert "acetylsalicylic acid" in agent["context"]["compound"]["synonyms"]
    assert agent["context"]["evidence_evals"]["total"] == 9
    assert agent["context"]["source_catalog"]["pubchem"]["release_phase"] == "P1 active"
    assert agent["model_request"]["messages"][0]["role"] == "system"

    repeated, repeated_path = install_builtin_example(manager, "medchem-lite")
    assert not repeated
    assert repeated_path == path
