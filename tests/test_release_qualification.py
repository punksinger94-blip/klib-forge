import importlib.util
import json
import sqlite3
import stat
import zipfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from klib_api.main import app
from klib_core import ForgeEngine, LibraryManager
from klib_core.database import Database
from klib_core.errors import KlibError, LibraryNotFoundError, ModelProviderError
from klib_core.files import chunk_text
from klib_core.mcp_server import _handle_line
from klib_core.providers import OpenAICompatibleProvider
from klib_core.vectors import ChromaVectorIndex, LocalVectorIndex, QdrantVectorIndex


def load_script_module(path: str):
    spec = importlib.util.spec_from_file_location("script_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_import_preserves_sources_and_rebuilds_indexes(tmp_path: Path) -> None:
    source_manager = LibraryManager(tmp_path / "source-home")
    source_manager.create("Portable", library_id="portable")
    source = tmp_path / "guide.md"
    source.write_text("Portable packages retain searchable source evidence.", encoding="utf-8")
    source_manager.add_sources("portable", source)
    ForgeEngine(source_manager).compile("portable")

    archive = source_manager.export("portable", tmp_path / "portable.klib")
    imported_manager = LibraryManager(tmp_path / "import-home")
    imported_manager.import_package(archive)

    imported_sources = imported_manager.sources("portable")
    assert len(imported_sources) == 1
    assert imported_sources[0]["title"] == "guide.md"
    compile_result = ForgeEngine(imported_manager).compile("portable")
    assert compile_result.sources == 1
    assert ForgeEngine(imported_manager).search("portable", "searchable evidence")


def test_preview_registry_lists_flagship_and_demo_packages() -> None:
    registry = json.loads(Path("examples/registry.json").read_text(encoding="utf-8"))
    assert registry["registry_version"] == "registry-preview.1"
    packages = {item["id"]: item for item in registry["packages"]}
    assert packages["medchem-lite"]["knowledge_ir_version"] == "medchem-ir-preview.1"
    assert packages["medchem-lite"]["validator_profile"] == "rdkit-medchem-preview"
    assert packages["biology-core-reference"]["hermes_mcp"] == "klib_forge"


def test_medchem_hermes_discovery_extracts_klib_import_plan() -> None:
    module = load_script_module("scripts/run-medchem-hermes-internet-klib.py")
    output = """
BEGIN_MEDCHEM_DISCOVERY_JSON
{
  "compound_query": "Advil",
  "active_compound_names": ["ibuprofen", "Advil (brand)", "Motrin (brand)"],
  "pubchem": {"cids": ["3672"], "urls": ["https://pubchem.ncbi.nlm.nih.gov/compound/3672"]},
  "chembl": {"ids": [], "urls": []},
  "source_urls": ["https://pubchem.ncbi.nlm.nih.gov/compound/3672"],
  "candidate_targets": [],
  "candidate_bioactivity": [],
  "literature_notes": [],
  "license_notes": [],
  "uncertainty": [],
  "recommended_klib_imports": ["ibuprofen", "Nurofen (brand)", "PubChem CID 3672"]
}
END_MEDCHEM_DISCOVERY_JSON
"""
    parsed = module.parse_discovery_json(output)
    assert parsed["active_compound_names"] == ["ibuprofen", "Advil (brand)", "Motrin (brand)"]
    identifiers = module.pubchem_identifiers("Advil", {"parsed": parsed})
    assert identifiers == ["ibuprofen", "Advil", "Motrin", "Nurofen"]
    assert module.clean_pubchem_identifier("Brufen (brand)") == "Brufen"
    assert module.resolve_base_url("b-ai", None) == "https://api.b.ai/v1"
    assert module.resolve_api_key_env("b-ai", None) == "BAI_API_KEY"
    assert module.messages_to_prompt(
        [
            {"role": "system", "content": "Use only K-LIB."},
            {"role": "user", "content": "Summarize Advil."},
        ]
    ) == "SYSTEM:\nUse only K-LIB.\n\nUSER:\nSummarize Advil."


def test_desktop_csp_allows_local_medchem_structure_images() -> None:
    config = json.loads(Path("apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    csp = config["app"]["security"]["csp"]
    assert "img-src" in csp
    assert "http://127.0.0.1:*" in csp
    assert "http://localhost:*" in csp


def test_import_restores_nested_sources_with_duplicate_filenames(tmp_path: Path) -> None:
    source_manager = LibraryManager(tmp_path / "source-home")
    source_manager.create("Nested", library_id="nested")
    library_path = source_manager.get("nested")[1]
    first = library_path / "sources" / "one" / "guide.md"
    second = library_path / "sources" / "two" / "guide.md"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text("First nested source.", encoding="utf-8")
    second.write_text("Second nested source.", encoding="utf-8")
    source_manager.register(library_path)

    archive = source_manager.export("nested", tmp_path / "nested.klib")
    imported_manager = LibraryManager(tmp_path / "import-home")
    imported_manager.import_package(archive)

    sources = imported_manager.sources("nested")
    assert len(sources) == 2
    assert len({source["id"] for source in sources}) == 2
    assert {source["path"] for source in sources} == {
        "sources\\one\\guide.md",
        "sources\\two\\guide.md",
    }


def test_failed_compile_preserves_last_good_database_and_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = LibraryManager(tmp_path / "home")
    manager.create("Atomic", library_id="atomic")
    source = tmp_path / "source.txt"
    source.write_text("The stable value is alpha.", encoding="utf-8")
    manager.add_sources("atomic", source)
    engine = ForgeEngine(manager)
    engine.compile("atomic")
    before = engine.search("atomic", "alpha")
    assert before

    source_record = manager.sources("atomic")[0]
    library_path = manager.get("atomic")[1]
    (library_path / source_record["path"]).write_text(
        "The replacement value is beta.",
        encoding="utf-8",
    )

    def fail_build(*_args, **_kwargs) -> None:
        raise KlibError("simulated adapter failure")

    monkeypatch.setattr("klib_core.engine.LocalVectorIndex.build", fail_build)
    with pytest.raises(KlibError, match="simulated adapter failure"):
        engine.compile("atomic")

    assert engine.search("atomic", "alpha")
    assert not engine.search("atomic", "beta")
    rows = manager.db.fetch_all(
        "SELECT text FROM chunks WHERE library_id = ?",
        ("atomic",),
    )
    assert any("alpha" in row["text"] for row in rows)


def test_database_commit_failure_restores_last_good_indexes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = LibraryManager(tmp_path / "home")
    manager.create("Atomic DB", library_id="atomic-db")
    source = tmp_path / "source.txt"
    source.write_text("The stable value is alpha.", encoding="utf-8")
    manager.add_sources("atomic-db", source)
    engine = ForgeEngine(manager)
    engine.compile("atomic-db")

    source_record = manager.sources("atomic-db")[0]
    library_path = manager.get("atomic-db")[1]
    (library_path / source_record["path"]).write_text(
        "The replacement value is beta.",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        manager.db,
        "replace_chunks",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("fail")),
    )

    with pytest.raises(sqlite3.OperationalError, match="fail"):
        engine.compile("atomic-db")
    assert engine.search("atomic-db", "alpha")
    assert not engine.search("atomic-db", "beta")


def test_refused_external_delete_keeps_registration(tmp_path: Path) -> None:
    manager = LibraryManager(tmp_path / "home")
    external = tmp_path / "external-library"
    manager.create("External", library_id="external", path=external)

    with pytest.raises(KlibError, match="outside"):
        manager.delete("external", remove_files=True)

    assert manager.get("external")[1] == external.resolve()
    assert external.exists()


def test_duplicate_library_id_cannot_replace_existing_registration(tmp_path: Path) -> None:
    manager = LibraryManager(tmp_path / "home")
    original = tmp_path / "original"
    manager.create("Original", library_id="same-id", path=original)

    with pytest.raises(KlibError, match="already registered"):
        manager.create("Replacement", library_id="same-id", path=tmp_path / "replacement")

    assert manager.get("same-id")[1] == original.resolve()


def test_eval_ids_and_payloads_are_strictly_validated(tmp_path: Path) -> None:
    manager = LibraryManager(tmp_path / "home")
    manager.create("Eval Safety", library_id="eval-safety")
    library_path = manager.get("eval-safety")[1]

    with pytest.raises(KlibError, match="Eval id"):
        manager.save_eval(
            "eval-safety",
            {"id": "../../escape", "input": "Question", "checks": {}},
        )
    assert not (library_path.parent / "escape.json").exists()

    with pytest.raises(KlibError, match="invalid"):
        manager.save_eval(
            "eval-safety",
            {"id": "bad-eval", "input": "", "checks": {"unknown": True}},
        )


def test_import_rejects_mismatched_root_symlink_and_oversized_member(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = LibraryManager(tmp_path / "home")
    manifest = {
        "id": "safe-package",
        "name": "Safe package",
        "version": "0.1.0",
        "klib_format_version": "0.1",
        "retrieval_policy": {
            "top_k": 8,
            "use_hybrid_search": False,
            "require_citations": True,
        },
        "model_policy": {
            "default_provider": "mock",
            "default_model": "offline",
            "allow_online_models": False,
        },
    }

    mismatch = tmp_path / "mismatch.klib"
    with zipfile.ZipFile(mismatch, "w") as archive:
        archive.writestr("wrong-root/manifest.json", json.dumps(manifest))
    with pytest.raises(KlibError, match="match manifest id"):
        manager.import_package(mismatch)

    symlink = tmp_path / "symlink.klib"
    with zipfile.ZipFile(symlink, "w") as archive:
        archive.writestr("safe-package/manifest.json", json.dumps(manifest))
        info = zipfile.ZipInfo("safe-package/sources/link.txt")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "../../outside.txt")
    with pytest.raises(KlibError, match="symbolic link"):
        manager.import_package(symlink)

    oversized = tmp_path / "oversized.klib"
    with zipfile.ZipFile(oversized, "w") as archive:
        archive.writestr("safe-package/manifest.json", json.dumps(manifest))
        archive.writestr("safe-package/sources/large.txt", b"x" * 1024)
    monkeypatch.setattr("klib_core.library.MAX_ARCHIVE_MEMBER_BYTES", 100)
    with pytest.raises(KlibError, match="too large"):
        manager.import_package(oversized)


def test_chunking_honors_size_and_rejects_invalid_configuration() -> None:
    text = ("a" * 900) + "\n\n" + ("b" * 900)
    chunks = chunk_text(text, size=1000, overlap=200)
    assert chunks
    assert all(len(chunk) <= 1000 for chunk in chunks)

    with pytest.raises(KlibError, match="size"):
        chunk_text("text", size=0, overlap=0)
    with pytest.raises(KlibError, match="overlap"):
        chunk_text("text", size=100, overlap=100)


def test_database_migrates_legacy_model_runs_prompt_column(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE model_runs (
                id TEXT PRIMARY KEY,
                library_id TEXT NOT NULL,
                provider TEXT,
                model TEXT,
                input TEXT,
                output TEXT,
                retrieved_context_json TEXT,
                latency_ms INTEGER,
                created_at TEXT
            );
            """
        )

    Database(database_path)
    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(model_runs)").fetchall()
        }
    assert "prompt" in columns


def test_provider_retry_clamps_negative_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    responses = [
        httpx.Response(429, request=request, headers={"retry-after": "-10"}),
        httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": "ok"}}]},
        ),
    ]
    delays: list[float] = []
    monkeypatch.setattr(
        "klib_core.providers.httpx.post",
        lambda *args, **kwargs: responses.pop(0),
    )
    monkeypatch.setattr("klib_core.providers.time.sleep", delays.append)

    provider = OpenAICompatibleProvider("https://example.test/v1", "secret")
    assert provider.chat([{"role": "user", "content": "test"}], "model", {}) == "ok"
    assert delays == [0]


def test_mcp_line_protocol_handles_notifications_parse_and_tool_errors(
    tmp_path: Path,
) -> None:
    home = tmp_path / "mcp-home"
    notification = _handle_line(
        '{"jsonrpc":"2.0","method":"notifications/initialized"}',
        home,
    )
    assert notification is None

    parse_error = _handle_line("{bad json", home)
    assert parse_error is not None
    assert parse_error["id"] is None
    assert parse_error["error"]["code"] == -32700

    tool_error = _handle_line(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "missing", "arguments": {}},
            }
        ),
        home,
    )
    assert tool_error is not None
    assert tool_error["id"] == 7
    assert tool_error["result"]["isError"] is True


def test_api_error_contract_and_request_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KLIB_HOME", str(tmp_path / "api-home"))
    client = TestClient(app)

    missing = client.get("/libraries/missing")
    assert missing.status_code == 404

    client.post("/libraries", json={"name": "Validation", "id": "validation"})
    source = client.post(
        "/libraries/validation/sources",
        files={"file": ("source.txt", b"safe source", "text/plain")},
    ).json()[0]
    invalid_trust = client.patch(
        f"/libraries/validation/sources/{source['id']}",
        json={"trust_level": "anything-goes"},
    )
    assert invalid_trust.status_code == 422

    invalid_arena = client.post(
        "/libraries/validation/arena",
        json={"models": [{"name": "one", "provider": "mock", "model": "offline"}]},
    )
    assert invalid_arena.status_code == 422

    invalid_top_k = client.get(
        "/libraries/validation/search",
        params={"q": "safe", "top_k": 0},
    )
    assert invalid_top_k.status_code == 422


def test_online_model_policy_blocks_provider_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = LibraryManager(tmp_path / "home")
    manager.create("Private", library_id="private")
    called = False

    def forbidden_provider(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider should not be created")

    monkeypatch.setattr("klib_core.engine.get_provider", forbidden_provider)
    with pytest.raises(KlibError, match="blocks online models"):
        ForgeEngine(manager).ask(
            "private",
            "send this",
            provider="openai",
            model="gpt-test",
        )
    assert called is False


def test_missing_library_uses_specific_exception(tmp_path: Path) -> None:
    manager = LibraryManager(tmp_path / "home")
    with pytest.raises(LibraryNotFoundError):
        manager.get("missing")


def test_openai_provider_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from klib_core.providers import get_provider

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ModelProviderError, match="OPENAI_API_KEY"):
        get_provider("openai")


def test_vector_adapter_failure_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = tmp_path / "broken-vectors.json"
    broken.write_text("{broken", encoding="utf-8")
    with pytest.raises(KlibError, match="unreadable"):
        LocalVectorIndex(broken).search("query", 3)

    with pytest.raises(KlibError, match="requires"):
        ChromaVectorIndex(tmp_path / "chroma", "collection").build([])

    requests: list[tuple[str, str]] = []
    request = httpx.Request("DELETE", "http://qdrant.test/collections/test")

    def fake_delete(url: str, **_kwargs) -> httpx.Response:
        requests.append(("DELETE", url))
        return httpx.Response(404, request=request)

    def fake_put(url: str, **_kwargs) -> httpx.Response:
        requests.append(("PUT", url))
        return httpx.Response(200, request=httpx.Request("PUT", url), json={"result": True})

    monkeypatch.setattr("klib_core.vectors.httpx.delete", fake_delete)
    monkeypatch.setattr("klib_core.vectors.httpx.put", fake_put)
    QdrantVectorIndex("http://qdrant.test", "test").build([])
    assert requests == [
        ("DELETE", "http://qdrant.test/collections/test"),
        ("PUT", "http://qdrant.test/collections/test"),
    ]

    monkeypatch.setattr(
        "klib_core.vectors.httpx.post",
        lambda url, **_kwargs: httpx.Response(
            503,
            request=httpx.Request("POST", url),
        ),
    )
    with pytest.raises(KlibError, match="Qdrant search failed"):
        QdrantVectorIndex("http://qdrant.test", "test").search("query", 3)
