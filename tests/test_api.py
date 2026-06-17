from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from klib_api.main import app
from klib_core.medchem import rdkit_available


def test_api_health_and_library_flow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KLIB_HOME", str(tmp_path / "api-home"))
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["version"] == "1.0.0"
    capabilities = client.get("/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["vector_adapters"]["local"] is True
    assert capabilities.json()["vector_adapters"]["qdrant"] is True

    created = client.post(
        "/libraries",
        json={
            "name": "API Demo",
            "id": "api-demo",
            "domain": "testing",
            "description": "API integration test",
        },
    )
    assert created.status_code == 201

    source = client.post(
        "/libraries/api-demo/sources",
        files={"file": ("guide.md", b"Local retrieval finds compiled knowledge.", "text/markdown")},
    )
    assert source.status_code == 201

    compiled = client.post("/libraries/api-demo/compile")
    assert compiled.status_code == 200
    assert compiled.json()["chunks"] == 1

    asked = client.post(
        "/libraries/api-demo/ask",
        json={"input": "What does local retrieval find?", "provider": "mock", "model": "offline"},
    )
    assert asked.status_code == 200
    assert asked.json()["retrieved_context"]


def test_builtin_examples_are_advanced_ready_and_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("KLIB_HOME", str(tmp_path / "example-home"))
    client = TestClient(app)

    catalog = client.get("/examples")
    assert catalog.status_code == 200
    assert {item["id"] for item in catalog.json()} == {
        "biomedical-evidence-synthesis",
        "medchem-lite",
        "production-incident-response",
    }

    installed = client.post("/examples/biomedical-evidence-synthesis/install")
    assert installed.status_code == 201
    assert installed.json()["created"] is True
    assert installed.json()["library"]["source_count"] == 5
    assert installed.json()["library"]["eval_count"] == 5

    asked = client.post(
        "/libraries/biomedical-evidence-synthesis/ask",
        json={
            "input": "Which small RNA regulates ompX at 37 C?",
            "provider": "mock",
            "model": "offline-demo",
        },
    )
    assert asked.status_code == 200
    assert "CyaR" in asked.json()["output"]
    assert "ompX" in asked.json()["output"]

    incident = client.post("/examples/production-incident-response/install")
    assert incident.status_code == 201
    assert incident.json()["library"]["source_count"] == 3
    assert incident.json()["library"]["eval_count"] == 3

    repeated = client.post("/examples/biomedical-evidence-synthesis/install")
    assert repeated.status_code == 201
    assert repeated.json()["created"] is False

    missing = client.post("/examples/does-not-exist/install")
    assert missing.status_code == 404


@pytest.mark.skipif(not rdkit_available(), reason="RDKit optional extra is not installed")
def test_api_bootstraps_configured_examples(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KLIB_HOME", str(tmp_path / "bootstrap-home"))
    monkeypatch.setenv("KLIB_BOOTSTRAP_EXAMPLES", "medchem-lite")

    with TestClient(app) as client:
        libraries = client.get("/libraries")

    assert libraries.status_code == 200
    assert any(item["id"] == "medchem-lite" for item in libraries.json())


@pytest.mark.skipif(not rdkit_available(), reason="RDKit optional extra is not installed")
def test_medchem_api_workflow_is_visible_end_to_end(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("KLIB_HOME", str(tmp_path / "medchem-home"))
    client = TestClient(app)

    capabilities = client.get("/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["medchem"]["available"] is True

    installed = client.post("/examples/medchem-lite/install")
    assert installed.status_code == 201
    assert installed.json()["library"]["manifest"]["domain"] == (
        "chemistry/medicinal-chemistry"
    )
    assert installed.json()["library"]["manifest"]["description"].startswith(
        "MedChem-KLIB Lite turns molecular structures"
    )

    status = client.get("/libraries/medchem-lite/medchem/status")
    assert status.status_code == 200
    assert status.json()["imported_compounds"] == 6
    assert status.json()["compiled_compounds"] == 5
    assert status.json()["invalid_compounds"] == 1
    assert status.json()["evidence"]["targets"] == 3
    assert status.json()["evidence"]["test_environments"] == 2
    assert status.json()["evidence"]["bioactivity_records"] == 5
    assert status.json()["evidence"]["literature_records"] == 4
    assert status.json()["evidence"]["missing_compound_provenance"] == []
    assert status.json()["evidence"]["ready"] is True

    sources = client.get("/medchem/sources")
    assert sources.status_code == 200
    assert sources.json()["pubchem"]["release_phase"] == "P1 active"
    assert sources.json()["chembl"]["release_phase"] == "P2 planned"
    assert sources.json()["zinc"]["release_phase"] == "P3 planned"

    validation = client.get("/libraries/medchem-lite/medchem/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] == 5
    assert validation.json()["invalid"] == 1

    compiled = client.post("/libraries/medchem-lite/medchem/compile")
    assert compiled.status_code == 200
    assert compiled.json()["unique_scaffolds"] == 2
    assert {item["code"] for item in compiled.json()["diagnostics"]} >= {
        "CHEM-W020",
        "CHEM-W040",
    }
    assert compiled.json()["duplicate_identity_groups"] == []

    compounds = client.get("/libraries/medchem-lite/medchem/compounds?query=aspirin")
    assert compounds.status_code == 200
    assert compounds.json()[0]["name"] == "Aspirin"

    structure = client.get(
        "/medchem/structure.svg",
        params={
            "smiles": "CC(=O)Oc1ccccc1C(=O)O",
            "width": 240,
            "height": 140,
        },
    )
    assert structure.status_code == 200
    assert structure.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in structure.text

    structure_3d = client.get(
        "/medchem/structure3d.sdf",
        params={"smiles": "CC(=O)Oc1ccccc1C(=O)O"},
    )
    assert structure_3d.status_code == 200
    assert structure_3d.headers["content-type"].startswith("chemical/x-mdl-sdfile")
    assert "K-LIB Forge 3D conformer" in structure_3d.text

    environments = client.get("/libraries/medchem-lite/medchem/environments")
    assert environments.status_code == 200
    assert environments.json()[0]["record_type"] == "test_environment"

    research = client.post(
        "/libraries/medchem-lite/medchem/research",
        json={"question": "Summarize the evidence for aspirin."},
    )
    assert research.status_code == 200
    assert research.json()["allowed"] is True
    assert "[1]" in research.json()["answer"]
    assert len(research.json()["citations"]) == 2

    agent = client.post(
        "/libraries/medchem-lite/medchem/agent",
        json={
            "question": "Summarize aspirin evidence and next data to import.",
            "provider": "mock",
            "model": "offline",
        },
    )
    assert agent.status_code == 200
    assert agent.json()["ready_for_review"] is True
    assert agent.json()["context"]["compound"]["name"] == "Aspirin"
    assert agent.json()["context"]["source_catalog"]["pubchem"]["release_phase"] == "P1 active"

    evidence_evals = client.post("/libraries/medchem-lite/medchem/evals")
    assert evidence_evals.status_code == 200
    assert evidence_evals.json()["score"] == 100
    assert evidence_evals.json()["total"] == 9

    similar = client.post(
        "/libraries/medchem-lite/medchem/similar",
        json={"smiles": "CC(=O)Oc1ccccc1C(=O)O", "top_k": 2},
    )
    assert similar.status_code == 200
    assert similar.json()[0]["name"] == "Aspirin"
    assert similar.json()[0]["tanimoto"] == 1.0

    blocked = client.post(
        "/medchem/safety-check",
        json={"request": "Give me step-by-step synthesis instructions for compound X."},
    )
    assert blocked.status_code == 200
    assert blocked.json()["allowed"] is False


def test_api_model_catalog_uses_shared_provider_registry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("KLIB_HOME", str(tmp_path / "models-home"))
    providers = TestClient(app).get("/models")
    assert providers.status_code == 200
    ids = {item["provider"] for item in providers.json()}
    assert {
        "anthropic",
        "azure-openai",
        "b-ai",
        "bedrock",
        "gemini",
        "nvidia",
        "openai-compatible",
        "vllm",
    } <= ids


def test_api_editor_suggestions_history_profiles_and_arena(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("KLIB_HOME", str(tmp_path / "roadmap-home"))
    client = TestClient(app)
    client.post("/libraries", json={"name": "Roadmap", "id": "roadmap"})
    source = client.post(
        "/libraries/roadmap/sources",
        files={
            "file": (
                "facts.md",
                b"Latency is response time. Latency must be measured.",
                "text/markdown",
            )
        },
    ).json()[0]
    assert client.patch(
        f"/libraries/roadmap/sources/{source['id']}",
        json={"trust_level": "trusted"},
    ).status_code == 200
    assert client.post("/libraries/roadmap/compile").status_code == 200
    assert client.get("/libraries/roadmap/suggestions").status_code == 200

    glossary = client.post(
        "/libraries/roadmap/glossary",
        json={"source_term": "latency", "target_term": "response time"},
    ).json()
    assert client.delete(
        f"/libraries/roadmap/glossary/{glossary['id']}"
    ).status_code == 204

    asked = client.post(
        "/libraries/roadmap/ask",
        json={"input": "What is latency?", "provider": "mock", "model": "offline"},
    )
    assert asked.status_code == 200
    assert client.get("/libraries/roadmap/runs").json()[0]["prompt"]

    profile = client.post(
        "/model-profiles",
        json={"name": "Offline", "provider": "mock", "model": "offline"},
    )
    assert profile.status_code == 201
    assert client.get("/model-profiles").json()
    assert client.delete(f"/model-profiles/{profile.json()['id']}").status_code == 204

    correction = client.post(
        "/libraries/roadmap/correct",
        json={
            "input": "What is latency?",
            "bad_output": "Delay",
            "corrected_output": "Response time",
            "lesson": "Use the glossary",
        },
    ).json()
    reviewed = client.post(
        f"/libraries/roadmap/corrections/{correction['id']}/review",
        json={"status": "approved"},
    )
    assert reviewed.json()["status"] == "approved"

    arena = client.post(
        "/libraries/roadmap/arena",
        json={
            "models": [
                {"name": "one", "provider": "mock", "model": "offline"},
                {"name": "two", "provider": "mock", "model": "offline"},
            ]
        },
    )
    assert arena.status_code == 200
    assert len(arena.json()["models"]) == 2
