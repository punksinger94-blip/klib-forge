from __future__ import annotations

import json
from pathlib import Path

import pytest
from klib_core import ForgeEngine, LibraryManager
from klib_core.errors import KlibError


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[LibraryManager, ForgeEngine, Path]:
    manager = LibraryManager(tmp_path / "home")
    library_path = tmp_path / "demo"
    manager.create(
        "Demo Library",
        library_id="demo-library",
        domain="software",
        path=library_path,
    )
    engine = ForgeEngine(manager)
    return manager, engine, library_path


def test_create_compile_search_and_ask(
    workspace: tuple[LibraryManager, ForgeEngine, Path],
    tmp_path: Path,
) -> None:
    manager, engine, _ = workspace
    source = tmp_path / "guide.md"
    source.write_text(
        "# Deployment\n\nLatency measures application response time after deployment.",
        encoding="utf-8",
    )

    added = manager.add_sources("demo-library", source)
    manager.add_glossary("demo-library", "latency", "response time")
    manager.add_rule("demo-library", "Keep API names in English.", priority=1)
    manager.add_example("demo-library", "High latency", "High response time")

    result = engine.compile("demo-library")
    assert result.sources == 1
    assert result.chunks >= 1
    assert "latency" in result.keywords

    search = engine.search("demo-library", "latency deployment")
    assert search
    assert search[0].source_id == added[0]["id"]

    answer = engine.ask(
        "demo-library",
        "What is latency after deployment?",
        provider="mock",
        model="offline-demo",
    )
    assert answer.provider == "mock"
    assert answer.retrieved_context
    assert "Latency" in answer.output


def test_correction_eval_and_diff(
    workspace: tuple[LibraryManager, ForgeEngine, Path],
    tmp_path: Path,
) -> None:
    manager, engine, library_path = workspace
    source = tmp_path / "facts.txt"
    source.write_text("Preferred output contains response time.", encoding="utf-8")
    manager.add_sources("demo-library", source)
    engine.compile("demo-library")

    correction = engine.correct(
        "demo-library",
        input_text="Explain latency",
        bad_output="It is delay.",
        corrected_output="It is response time.",
        must_include=["response time"],
    )
    assert correction["created_eval_id"]
    eval_path = library_path / "evals" / f"{correction['created_eval_id']}.json"
    assert eval_path.exists()

    diff = engine.diff("demo-library")
    assert correction["created_eval_id"] in diff.added_evals

    results = engine.run_evals("demo-library", provider="mock", model="offline-demo")
    assert len(results) == 1
    assert results[0].score == 100


def test_export_import_and_archive_safety(
    workspace: tuple[LibraryManager, ForgeEngine, Path],
    tmp_path: Path,
) -> None:
    manager, _, _ = workspace
    archive = manager.export("demo-library", tmp_path / "demo.klib")
    assert archive.exists()

    imported_manager = LibraryManager(tmp_path / "import-home")
    imported = imported_manager.import_package(archive)
    assert imported.id == "demo-library"
    assert imported_manager.get("demo-library")[1].exists()

    unsafe = tmp_path / "unsafe.klib"
    import zipfile

    with zipfile.ZipFile(unsafe, "w") as package:
        package.writestr("../escape.txt", "bad")
    with pytest.raises(KlibError):
        imported_manager.import_package(unsafe)


def test_manifest_is_valid_json(workspace: tuple[LibraryManager, ForgeEngine, Path]) -> None:
    _, _, library_path = workspace
    data = json.loads((library_path / "manifest.json").read_text(encoding="utf-8"))
    assert data["klib_format_version"] == "0.1"
    assert data["model_policy"]["allow_online_models"] is False

