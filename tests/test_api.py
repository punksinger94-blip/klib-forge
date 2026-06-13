from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from klib_api.main import app


def test_api_health_and_library_flow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KLIB_HOME", str(tmp_path / "api-home"))
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["version"] == "1.0.0"

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


def test_builtin_example_install_is_ready_and_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("KLIB_HOME", str(tmp_path / "example-home"))
    client = TestClient(app)

    installed = client.post("/examples/arabic-technical-translation/install")
    assert installed.status_code == 201
    assert installed.json()["created"] is True
    assert installed.json()["library"]["source_count"] == 1
    assert installed.json()["library"]["eval_count"] == 1

    asked = client.post(
        "/libraries/arabic-technical-translation/ask",
        json={
            "input": "Translate: high latency after deployment.",
            "provider": "mock",
            "model": "offline-demo",
        },
    )
    assert asked.status_code == 200
    assert "زمن الاستجابة" in asked.json()["output"]
    assert "النشر" in asked.json()["output"]

    repeated = client.post("/examples/arabic-technical-translation/install")
    assert repeated.status_code == 201
    assert repeated.json()["created"] is False


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
