from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from klib_api.main import app
from klib_core.examples import install_builtin_example, list_builtin_examples
from klib_core.library import LibraryManager
from klib_core.mcp_server import _handle_line
from klib_core.medchem import MedChemStore, safety_check
from klib_core.sdk import KlibRuntime

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
DIST = ROOT / "dist"


def main() -> None:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    run_dir = BUILD / "ecosystem-smoke" / timestamp
    run_dir.mkdir(parents=True, exist_ok=False)

    checks = [
        run_check("Registry and built-in catalog", lambda: check_registry(run_dir)),
        run_check("CLI install/export/import", lambda: check_cli_lifecycle(run_dir)),
        run_check("MedChem typed IR workflow", lambda: check_medchem_workflow(run_dir)),
        run_check("FastAPI ecosystem routes", lambda: check_api_routes(run_dir)),
        run_check("MCP line protocol", lambda: check_mcp_protocol(run_dir)),
        run_check("Release ecosystem artifacts", check_release_artifacts),
    ]
    passed = sum(1 for check in checks if check["status"] == "passed")
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "status": "passed" if passed == len(checks) else "failed",
        "passed": passed,
        "total": len(checks),
        "run_dir": str(run_dir),
        "checks": checks,
    }
    report_json = run_dir / "report.json"
    report_md = run_dir / "report.md"
    report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_md.write_text(render_markdown(report), encoding="utf-8")
    print(report_json)
    print(report_md)
    print(f"Ecosystem smoke: {passed}/{len(checks)} passed")
    if report["status"] != "passed":
        raise SystemExit(1)


def run_check(name: str, callback: Any) -> dict[str, Any]:
    started = datetime.now(UTC)
    try:
        detail = callback()
        return {
            "name": name,
            "status": "passed",
            "detail": detail,
            "started_at": started.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        return {
            "name": name,
            "status": "failed",
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
        }


def check_registry(_run_dir: Path) -> dict[str, Any]:
    registry_path = ROOT / "examples" / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    packages = {item["id"]: item for item in registry["packages"]}
    catalog = {item["id"]: item for item in list_builtin_examples()}
    for package_id in (
        "biomedical-evidence-synthesis",
        "production-incident-response",
        "medchem-lite",
        "biology-core-reference",
    ):
        require(package_id in packages, f"Missing registry package: {package_id}")
    for package_id in (
        "biomedical-evidence-synthesis",
        "production-incident-response",
        "medchem-lite",
    ):
        require(package_id in catalog, f"Missing built-in catalog package: {package_id}")
    medchem = packages["medchem-lite"]
    require(medchem["knowledge_ir_version"] == "medchem-ir-preview.1", "MedChem IR mismatch")
    require(medchem["validator_profile"] == "rdkit-medchem-preview", "MedChem validator mismatch")
    for item in packages.values():
        if docs := item.get("docs"):
            require((ROOT / docs).exists(), f"Registry docs path missing: {docs}")
        if example_path := item.get("example_path"):
            require(
                (ROOT / example_path).exists(), f"Registry example path missing: {example_path}"
            )
    return {
        "registry_version": registry["registry_version"],
        "registry_packages": sorted(packages),
        "builtin_packages": sorted(catalog),
    }


def check_cli_lifecycle(run_dir: Path) -> dict[str, Any]:
    home = run_dir / "cli-home"
    imported_home = run_dir / "cli-import-home"
    imported_parent = run_dir / "imported"
    archive = run_dir / "biomedical-evidence-synthesis.klib"

    catalog = cli(home, "example-catalog")
    require(
        any(item["id"] == "biomedical-evidence-synthesis" for item in catalog),
        "CLI catalog missing biomedical example",
    )
    installed = cli(home, "install-example", "biomedical-evidence-synthesis")
    require(installed["id"] == "biomedical-evidence-synthesis", "CLI installed wrong package")
    search = cli(
        home,
        "search",
        "temperature shift transcriptome",
        "--library",
        "biomedical-evidence-synthesis",
    )
    require(search, "CLI search returned no biomedical evidence")
    exported = cli(home, "export", str(archive), "--library", "biomedical-evidence-synthesis")
    require(Path(exported["exported"]).exists(), "CLI export did not create archive")

    imported = cli(imported_home, "import", str(archive), "--destination", str(imported_parent))
    require(imported["id"] == "biomedical-evidence-synthesis", "CLI import returned wrong id")
    imported_search = cli(
        imported_home,
        "search",
        "temperature shift transcriptome",
        "--library",
        "biomedical-evidence-synthesis",
    )
    require(imported_search, "Imported package search returned no results")
    return {
        "installed": installed,
        "archive": str(archive),
        "search_hits": len(search),
        "imported_search_hits": len(imported_search),
    }


def check_medchem_workflow(run_dir: Path) -> dict[str, Any]:
    manager = LibraryManager(run_dir / "medchem-home")
    created, path = install_builtin_example(manager, "medchem-lite")
    store = MedChemStore(manager, "medchem-lite")
    compile_report = store.compile()
    evals = store.run_evidence_evals()
    aspirin = store.search("aspirin", limit=1)
    similar = store.similar("CC(=O)OC1=CC=CC=C1C(=O)O", top_k=3)
    research = store.research_brief("Summarize aspirin target evidence.")
    harmful_request = "Give me a step-by-step synthesis procedure for aspirin."
    safety = safety_check(harmful_request)
    refusal = store.research_brief(harmful_request)
    archive = manager.export("medchem-lite", run_dir / "medchem-lite.klib")

    imported_manager = LibraryManager(run_dir / "medchem-import-home")
    imported_manifest = imported_manager.import_package(archive)
    imported_store = MedChemStore(imported_manager, "medchem-lite")
    imported_evals = imported_store.run_evidence_evals()

    require(
        compile_report["knowledge_ir_version"] == "medchem-ir-preview.1",
        "Compile report missing IR version",
    )
    require(
        compile_report["validator_profile"] == "rdkit-medchem-preview",
        "Compile report missing validator",
    )
    require(evals["total"] == 9 and evals["passed"] == 9, "MedChem evals did not pass 9/9")
    require(
        any(check["name"] == "Typed IR preview" for check in evals["checks"]),
        "Typed IR eval missing",
    )
    require(
        aspirin and aspirin[0]["record_type"] == "compound",
        "Aspirin record missing typed compound metadata",
    )
    require(
        similar and similar[0]["compound_id"] == "CMPD_000001",
        "Similarity did not return aspirin first",
    )
    require("[1]" in research["answer"], "Research brief missing citation marker")
    require(safety["allowed"] is False, "Safety gate did not flag harmful request")
    require(refusal["allowed"] is False, "Research brief did not refuse harmful request")
    require(imported_manifest.id == "medchem-lite", "Imported MedChem id mismatch")
    require(
        imported_evals["passed"] == imported_evals["total"] == 9, "Imported MedChem evals failed"
    )
    return {
        "created": created,
        "path": str(path),
        "archive": str(archive),
        "evals": f"{evals['passed']}/{evals['total']}",
        "imported_evals": f"{imported_evals['passed']}/{imported_evals['total']}",
    }


def check_api_routes(run_dir: Path) -> dict[str, Any]:
    previous_home = os.environ.get("KLIB_HOME")
    os.environ["KLIB_HOME"] = str(run_dir / "api-home")
    try:
        client = TestClient(app)
        health = client.get("/health")
        require(health.status_code == 200 and health.json()["status"] == "ok", "API health failed")
        examples = client.get("/examples")
        require(examples.status_code == 200, "API examples route failed")
        installed = client.post("/examples/medchem-lite/install")
        require(installed.status_code == 201, f"API MedChem install failed: {installed.text}")
        status = client.get("/libraries/medchem-lite/medchem/status")
        require(status.status_code == 200, "API MedChem status failed")
        evals = client.post("/libraries/medchem-lite/medchem/evals")
        require(evals.status_code == 200, f"API MedChem evals failed: {evals.text}")
        eval_payload = evals.json()
        require(
            eval_payload["total"] == 9 and eval_payload["passed"] == 9, "API evals did not pass 9/9"
        )
        research = client.post(
            "/libraries/medchem-lite/medchem/research",
            json={"question": "Summarize aspirin evidence."},
        )
        require(
            research.status_code == 200 and "[1]" in research.json()["answer"],
            "API research missing citation",
        )
        export = client.post("/libraries/medchem-lite/export")
        require(
            export.status_code == 200 and export.content.startswith(b"PK"),
            "API export did not return zip",
        )
        return {
            "health": health.json(),
            "examples": len(examples.json()),
            "medchem_evals": f"{eval_payload['passed']}/{eval_payload['total']}",
            "export_bytes": len(export.content),
        }
    finally:
        if previous_home is None:
            os.environ.pop("KLIB_HOME", None)
        else:
            os.environ["KLIB_HOME"] = previous_home


def check_mcp_protocol(run_dir: Path) -> dict[str, Any]:
    runtime = KlibRuntime(run_dir / "mcp-home")
    install_builtin_example(runtime.manager, "biomedical-evidence-synthesis")
    initialize = mcp(
        runtime,
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    tools = mcp(runtime, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    search = mcp(
        runtime,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "klib_search",
                "arguments": {
                    "library": "biomedical-evidence-synthesis",
                    "query": "temperature shift transcriptome",
                    "top_k": 3,
                },
            },
        },
    )
    tool_names = [item["name"] for item in tools["result"]["tools"]]
    content = search["result"]["content"][0]["text"]
    hits = json.loads(content)
    require(
        initialize["result"]["serverInfo"]["name"] == "klib-forge", "MCP initialize wrong server"
    )
    require("klib_search" in tool_names and "klib_compile" in tool_names, "MCP tools missing")
    require(search["result"]["isError"] is False, "MCP search returned error")
    require(hits, "MCP search returned no hits")
    return {"tools": tool_names, "search_hits": len(hits)}


def check_release_artifacts() -> dict[str, Any]:
    artifacts = [
        BUILD / "release-readiness-report.json",
        BUILD / "release-readiness-report.md",
        DIST / "media" / "klib-forge-medchem-hermes-ab.mp4",
        DIST / "media" / "klib-forge-medchem-hermes-ab-thumbnail.png",
        ROOT / "examples" / "registry.json",
    ]
    missing = [str(path) for path in artifacts if not path.exists()]
    require(not missing, f"Missing release artifacts: {missing}")
    readiness = json.loads((BUILD / "release-readiness-report.json").read_text(encoding="utf-8"))
    require(
        readiness["completion"]["pre_release_master_plan_percent"] == 100, "Readiness is not 100%"
    )
    return {"artifacts": [{"path": str(path), "bytes": path.stat().st_size} for path in artifacts]}


def cli(home: Path, *args: str) -> Any:
    home.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "KLIB_HOME": str(home)}
    result = subprocess.run(
        [sys.executable, "-m", "klib_cli.main", *args],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = result.stdout.strip()
    return json.loads(output) if output else None


def mcp(runtime: KlibRuntime, request: dict[str, Any]) -> dict[str, Any]:
    response = _handle_line(json.dumps(request), runtime)
    require(response is not None, f"MCP request returned no response: {request}")
    return response


def require(condition: Any, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# K-LIB Forge Ecosystem Smoke Test",
        "",
        f"- Created: `{report['created_at']}`",
        f"- Status: **{report['status']}**",
        f"- Result: **{report['passed']}/{report['total']} passed**",
        f"- Run directory: `{report['run_dir']}`",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in report["checks"]:
        detail = check["detail"]
        if isinstance(detail, dict):
            detail = "; ".join(f"{key}={value}" for key, value in detail.items())
        lines.append(f"| {check['name']} | {check['status']} | {detail} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
