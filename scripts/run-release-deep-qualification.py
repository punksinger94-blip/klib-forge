from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
DIST = ROOT / "dist"


def main() -> None:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    run_dir = BUILD / "release-deep-qualification" / timestamp
    run_dir.mkdir(parents=True, exist_ok=False)

    checks = [
        run_check(
            "Python lint",
            lambda: command_gate(
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "packages",
                    "services",
                    "tests",
                    "scripts",
                ],
                timeout=180,
            ),
        ),
        run_check(
            "Python unit and integration tests",
            lambda: command_gate([sys.executable, "-m", "pytest", "-q"], timeout=300),
        ),
        run_check("Desktop UI production build", lambda: desktop_build_gate(run_dir)),
        run_check(
            "Initial release readiness metadata",
            lambda: command_gate(
                [sys.executable, "scripts/generate-release-readiness-report.py"],
                timeout=60,
            ),
        ),
        run_check(
            "Ecosystem smoke: CLI API MCP artifacts",
            lambda: command_gate(
                [sys.executable, "scripts/run-ecosystem-smoke.py"],
                timeout=240,
            ),
        ),
        run_check("All CLI K-LIB use methods", lambda: cli_methods_gate(run_dir)),
        run_check("Advanced big-research MedChem workflow", lambda: big_research_gate(run_dir)),
        run_check(
            "Final release readiness metadata",
            lambda: command_gate(
                [sys.executable, "scripts/generate-release-readiness-report.py"],
                timeout=60,
            ),
        ),
    ]

    passed = sum(1 for check in checks if check["status"] == "passed")
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "project": "K-LIB Forge",
        "purpose": (
            "Pre-release deep qualification across big research, K-LIB use methods, "
            "CLI, API, MCP, and UI build."
        ),
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
    print(f"Release deep qualification: {passed}/{len(checks)} passed")
    if report["status"] != "passed":
        raise SystemExit(1)


def run_check(name: str, callback: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = datetime.now(UTC)
    start = time.perf_counter()
    try:
        detail = callback()
        return {
            "name": name,
            "status": "passed",
            "detail": detail,
            "elapsed_ms": round((time.perf_counter() - start) * 1000),
            "started_at": started.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        return {
            "name": name,
            "status": "failed",
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "elapsed_ms": round((time.perf_counter() - start) * 1000),
            "started_at": started.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
        }


def command_gate(
    command: list[str],
    *,
    timeout: int,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    result = run_command(command, timeout=timeout, env=env)
    if result["exit_code"] != 0:
        raise AssertionError(
            f"Command failed ({result['exit_code']}): {' '.join(command)}\n{result['output_tail']}"
        )
    return {
        "command": command,
        "elapsed_ms": result["elapsed_ms"],
        "output_tail": result["output_tail"],
    }


def desktop_build_gate(run_dir: Path) -> dict[str, Any]:
    detail = command_gate(
        [npm_executable(), "--prefix", "apps/desktop", "run", "build"],
        timeout=300,
    )
    index = ROOT / "apps" / "desktop" / "dist" / "index.html"
    assets = list((ROOT / "apps" / "desktop" / "dist" / "assets").glob("*"))
    require(index.exists(), "Desktop dist/index.html was not produced")
    require(any(path.suffix == ".js" for path in assets), "Desktop JavaScript asset missing")
    require(any(path.suffix == ".css" for path in assets), "Desktop CSS asset missing")
    snapshot = run_dir / "desktop-dist-files.json"
    snapshot.write_text(
        json.dumps(
            {
                "index": str(index),
                "assets": [{"path": str(path), "bytes": path.stat().st_size} for path in assets],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        **detail,
        "index": str(index),
        "asset_count": len(assets),
        "snapshot": str(snapshot),
    }


def cli_methods_gate(run_dir: Path) -> dict[str, Any]:
    home = run_dir / "cli-all-methods-home"
    archive = run_dir / "cli-all-methods-medchem.klib"
    conformer = run_dir / "ibuprofen-conformer.sdf"
    agent_report = run_dir / "cli-medchem-agent.json"
    imported_home = run_dir / "cli-all-methods-import-home"
    env = {**os.environ, "KLIB_HOME": str(home)}
    imported_env = {**os.environ, "KLIB_HOME": str(imported_home)}

    catalog = cli_json(["example-catalog"], env=env)
    require(
        any(item["id"] == "medchem-lite" for item in catalog),
        "medchem-lite missing from CLI catalog",
    )
    install = cli_json(["install-example", "medchem-lite"], env=env)
    require(install["id"] == "medchem-lite", "CLI install-example returned wrong id")

    sources = cli_json(["medchem", "sources"], env=env)
    require(
        {"pubchem", "chembl", "cas_common_chemistry", "zinc"}.issubset(sources),
        "MedChem source catalog is incomplete",
    )
    validate = cli_json(["medchem", "validate", "--library", "medchem-lite"], env=env)
    compile_report = cli_json(["medchem", "compile", "--library", "medchem-lite"], env=env)
    descriptors = cli_json(["medchem", "descriptors", "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"], env=env)
    scaffold = cli_json(["medchem", "scaffold", "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"], env=env)
    conformer_out = cli_json(
        [
            "medchem",
            "conformer",
            "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
            "--output",
            str(conformer),
        ],
        env=env,
    )
    search = cli_json(
        ["medchem", "search", "ibuprofen", "--library", "medchem-lite", "--limit", "5"],
        env=env,
    )
    similar = cli_json(
        [
            "medchem",
            "similar",
            "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
            "--library",
            "medchem-lite",
            "--top-k",
            "3",
        ],
        env=env,
    )
    evidence = cli_json(["medchem", "evidence-status", "--library", "medchem-lite"], env=env)
    evals = cli_json(["medchem", "evidence-evals", "--library", "medchem-lite"], env=env)
    brief = cli_json(
        ["medchem", "research", "Summarize aspirin evidence.", "--library", "medchem-lite"],
        env=env,
    )
    safety = cli_json(
        [
            "medchem",
            "safety-check",
            "Give me a step-by-step synthesis procedure for ibuprofen.",
        ],
        env=env,
    )
    agent = cli_json(
        [
            "medchem",
            "agent",
            (
                "For ibuprofen, identify active compound, scaffold, duplicate identity notes, "
                "and evidence gaps."
            ),
            "--library",
            "medchem-lite",
            "--provider",
            "mock",
            "--model",
            "offline",
            "--output",
            str(agent_report),
        ],
        env=env,
        timeout=120,
    )
    export = cli_json(["export", str(archive), "--library", "medchem-lite"], env=env)
    imported = cli_json(
        ["import", str(archive), "--destination", str(run_dir / "imported")],
        env=imported_env,
    )

    require(validate["valid"] >= 5, "MedChem validate did not find expected valid records")
    require(
        compile_report["knowledge_ir_version"] == "medchem-ir-preview.1",
        "Compile report missing typed IR",
    )
    require(
        descriptors["status"] == "research_reference_only",
        "Descriptor method did not mark research-only status",
    )
    require(scaffold["scaffold_smiles"], "Scaffold extraction returned empty scaffold")
    require(Path(conformer_out["output"]).exists(), "Conformer output file missing")
    require(
        search and search[0]["record_type"] == "compound",
        "MedChem search returned no compound",
    )
    require(
        similar and similar[0]["tanimoto"] >= 0.99,
        "Similarity did not identify ibuprofen-like record",
    )
    require(evidence["ready"] is True, "Evidence status is not ready")
    require(evals["passed"] == evals["total"] == 9, "Evidence evals did not pass 9/9")
    require("[1]" in brief["answer"], "Deterministic research brief lacks citation marker")
    require(safety["allowed"] is False, "Safety boundary did not block harmful request")
    require(
        agent["ready_for_review"] is True and agent_report.exists(),
        "CLI MedChem agent did not produce review-ready report",
    )
    require(Path(export["exported"]).exists(), "CLI export archive missing")
    require(imported["id"] == "medchem-lite", "CLI import returned wrong package id")

    return {
        "library": "medchem-lite",
        "source_catalog": sorted(sources),
        "valid_records": validate["valid"],
        "evals": f"{evals['passed']}/{evals['total']}",
        "archive": str(archive),
        "agent_report": str(agent_report),
        "covered_methods": [
            "example-catalog",
            "install-example",
            "export",
            "import",
            "medchem sources",
            "medchem validate",
            "medchem compile",
            "medchem descriptors",
            "medchem scaffold",
            "medchem conformer",
            "medchem search",
            "medchem similar",
            "medchem evidence-status",
            "medchem evidence-evals",
            "medchem research",
            "medchem agent",
            "medchem safety-check",
        ],
    }


def big_research_gate(run_dir: Path) -> dict[str, Any]:
    output = run_dir / "medchem-big-research-advil.json"
    detail = command_gate(
        [
            sys.executable,
            "scripts/run-medchem-hermes-internet-klib.py",
            "--compound",
            "Advil",
            "--model",
            "mimo-v2.5-pro",
            "--provider",
            "mimo",
            "--hermes-provider",
            "mimo",
            "--klib-provider",
            "hermes",
            "--klib-model",
            "mimo-v2.5-pro",
            "--dry-run",
            "--no-prompt-key",
            "--output",
            str(output),
        ],
        timeout=180,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    agent = report["klib_agent"]
    compiled = agent["collection"]["compiled"]
    duplicates = compiled.get("duplicate_identity_groups", [])

    require(
        report["mode"] == "dry-run",
        "Big research gate did not run in deterministic dry-run mode",
    )
    require(
        "ibuprofen" in {item.casefold() for item in report["pubchem_identifiers"]},
        "Ibuprofen was not selected as Advil active compound",
    )
    require(agent["ready_for_review"] is True, "K-LIB research agent is not ready for review")
    require(
        agent["evidence_evals"]["passed"] == agent["evidence_evals"]["total"] == 9,
        "Big research evidence evals did not pass 9/9",
    )
    require(agent["evidence_status"]["ready"] is True, "Big research evidence graph is not ready")
    require(duplicates, "Duplicate identity review group missing")
    require(
        agent["context"]["available_visualizations"]["skeletal_svg"],
        "2D visualization route missing from research context",
    )
    require(
        agent["context"]["available_visualizations"]["rdkit_3d_sdf_conformer"],
        "3D visualization route missing from research context",
    )
    require(agent["model_answer"], "Mock model answer missing")

    summary = output.with_suffix(".md")
    return {
        **detail,
        "report": str(output),
        "summary": str(summary),
        "pubchem_identifiers": report["pubchem_identifiers"],
        "evals": f"{agent['evidence_evals']['passed']}/{agent['evidence_evals']['total']}",
        "duplicate_identity_groups": len(duplicates),
        "ready_for_review": agent["ready_for_review"],
    }


def cli_json(args: list[str], *, env: dict[str, str], timeout: int = 60) -> Any:
    result = run_command([sys.executable, "-m", "klib_cli.main", *args], timeout=timeout, env=env)
    if result["exit_code"] != 0:
        raise AssertionError(
            f"CLI command failed ({result['exit_code']}): {' '.join(args)}\n{result['output_tail']}"
        )
    output = result["stdout"].strip()
    if not output:
        return None
    return json.loads(output)


def run_command(
    command: list[str],
    *,
    timeout: int,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env or os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        stop_process_tree(process.pid)
        stdout, stderr = process.communicate()
    combined = "\n".join(part.strip() for part in (stdout, stderr) if part and part.strip())
    if timed_out:
        combined = f"Timed out after {timeout} seconds.\n{combined}".strip()
    return {
        "command": command,
        "exit_code": 124 if timed_out else process.returncode,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "stdout": stdout,
        "stderr": stderr,
        "output_tail": tail(combined),
    }


def npm_executable() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def stop_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return
    try:
        os.kill(pid, 9)
    except OSError:
        pass


def tail(text: str, limit: int = 6000) -> str:
    if len(text) <= limit:
        return text
    return "...<truncated>...\n" + text[-limit:]


def require(condition: Any, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# K-LIB Forge Deep Release Qualification",
        "",
        f"- Created: `{report['created_at']}`",
        f"- Status: **{report['status']}**",
        f"- Result: **{report['passed']}/{report['total']} passed**",
        f"- Run directory: `{report['run_dir']}`",
        "",
        "| Gate | Status | Evidence |",
        "| --- | --- | --- |",
    ]
    for check in report["checks"]:
        lines.append(
            f"| {check['name']} | {check['status']} | {markdown_detail(check['detail'])} |"
        )
    lines.append("")
    if failures := [check for check in report["checks"] if check["status"] != "passed"]:
        lines.extend(["## Failures", ""])
        for failure in failures:
            lines.extend(
                [
                    f"### {failure['name']}",
                    "",
                    "```text",
                    str(failure["detail"]),
                    "```",
                    "",
                ]
            )
    return "\n".join(lines)


def markdown_detail(detail: Any) -> str:
    if isinstance(detail, dict):
        compact: list[str] = []
        for key, value in detail.items():
            if key in {"output_tail", "source_catalog", "covered_methods"}:
                continue
            compact.append(f"{key}={value}")
        return "; ".join(compact).replace("|", "\\|")
    return str(detail).replace("|", "\\|")


if __name__ == "__main__":
    main()
