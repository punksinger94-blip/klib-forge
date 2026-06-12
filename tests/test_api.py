from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from klib_api.main import app


def test_api_health_and_library_flow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KLIB_HOME", str(tmp_path / "api-home"))
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["version"] == "0.1.1"

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
