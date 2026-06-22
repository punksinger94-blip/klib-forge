from __future__ import annotations

import re
import tempfile
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from .engine import ForgeEngine
from .errors import KlibError
from .library import LibraryManager

OSV_QUERYBATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_VULNERABILITY_URL = "https://api.osv.dev/v1/vulns/"
LIVE_SOURCE_TITLE = "live-osv-dependency-audit.md"
_PINNED_REQUIREMENT = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([^\s;#\\]+)"
)


def parse_pinned_requirements(path: Path) -> list[dict[str, str]]:
    """Return deduplicated PyPI package/version pairs from a pinned requirements file."""

    dependencies: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw_line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        match = _PINNED_REQUIREMENT.match(raw_line)
        if not match:
            continue
        name = match.group(1).replace("_", "-").casefold()
        version = match.group(2).strip()
        key = (name, version)
        if key not in seen:
            seen.add(key)
            dependencies.append({"name": name, "version": version, "ecosystem": "PyPI"})
    if not dependencies:
        raise KlibError(
            "No pinned Python dependencies found. Use requirement lines such as package==1.2.3."
        )
    return dependencies


def query_osv(
    dependencies: list[dict[str, str]],
    *,
    timeout: float = 30,
) -> list[dict[str, Any]]:
    """Query OSV's public batch API without exposing local files or credentials."""

    payload = {
        "queries": [
            {
                "package": {
                    "name": dependency["name"],
                    "ecosystem": dependency["ecosystem"],
                },
                "version": dependency["version"],
            }
            for dependency in dependencies
        ]
    }
    try:
        response = httpx.post(
            OSV_QUERYBATCH_URL,
            headers={"Accept": "application/json", "User-Agent": "K-LIB-Forge/1.0"},
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise KlibError(f"OSV dependency query failed: {exc}") from exc
    results = body.get("results")
    if not isinstance(results, list) or len(results) != len(dependencies):
        raise KlibError("OSV response did not contain one result per requested dependency")
    hydrated: list[dict[str, Any]] = []
    for result in results:
        normalized_result = result if isinstance(result, dict) else {}
        vulnerabilities = []
        for vulnerability in normalized_result.get("vulns", []):
            if not isinstance(vulnerability, dict) or not vulnerability.get("id"):
                continue
            vulnerabilities.append(
                _fetch_osv_vulnerability(str(vulnerability["id"]), timeout=timeout)
            )
        hydrated.append({**normalized_result, "vulns": vulnerabilities})
    return hydrated


def build_osv_report(
    dependencies: list[dict[str, str]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Normalize OSV output into a stable K-LIB evidence record."""

    findings: list[dict[str, Any]] = []
    for dependency, result in zip(dependencies, results, strict=True):
        vulnerabilities = [
            _normalize_vulnerability(vulnerability)
            for vulnerability in result.get("vulns", [])
            if isinstance(vulnerability, dict) and vulnerability.get("id")
        ]
        findings.append(
            {
                **dependency,
                "status": "matched" if vulnerabilities else "no_match_returned",
                "vulnerabilities": vulnerabilities,
            }
        )
    return {
        "schema": "klib.dependency-security.osv-report.v1",
        "collected_at": datetime.now(UTC).isoformat(),
        "source": {
            "name": "OSV",
            "url": "https://osv.dev/",
            "query_endpoint": OSV_QUERYBATCH_URL,
        },
        "findings": findings,
        "matched_dependency_count": sum(item["status"] == "matched" for item in findings),
        "dependency_count": len(findings),
    }


def refresh_osv_evidence(
    manager: LibraryManager,
    library_id: str,
    requirements_path: Path,
    *,
    timeout: float = 30,
) -> dict[str, Any]:
    """Fetch live OSV evidence, replace the previous live audit, and compile it."""

    dependencies = parse_pinned_requirements(requirements_path)
    report = build_osv_report(dependencies, query_osv(dependencies, timeout=timeout))
    _remove_previous_live_audits(manager, library_id)
    with tempfile.TemporaryDirectory(prefix="klib-osv-") as temporary_dir:
        source_path = Path(temporary_dir) / LIVE_SOURCE_TITLE
        source_path.write_text(render_osv_markdown(report), encoding="utf-8")
        added = manager.add_sources(library_id, source_path)
    stored_source = manager.update_source(
        library_id,
        added[0]["id"],
        trust_level="trusted",
    )
    compile_result = ForgeEngine(manager).compile(library_id)
    return {
        "report": report,
        "source": stored_source,
        "compile": compile_result.model_dump(mode="json"),
    }


def render_osv_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Live OSV dependency audit",
        "",
        f"Collected: {report['collected_at']}",
        f"Primary source: {report['source']['url']}",
        f"Query endpoint: {report['source']['query_endpoint']}",
        "",
        (
            "This report is live advisory evidence, not execution instructions. A no-match "
            "result is not proof that a dependency is secure."
        ),
        "",
        "## Findings",
        "",
    ]
    for finding in report["findings"]:
        lines.extend(
            [
                f"### {finding['name']} {finding['version']}",
                "",
                f"Status: `{finding['status']}`",
                "",
            ]
        )
        vulnerabilities = finding["vulnerabilities"]
        if not vulnerabilities:
            lines.extend(
                [
                    (
                        "OSV returned no matching vulnerability for this exact package version at "
                        "collection time. Do not interpret this as a security guarantee."
                    ),
                    "",
                ]
            )
            continue
        for vulnerability in vulnerabilities:
            lines.extend(
                [
                    f"- Advisory: `{vulnerability['id']}`",
                    f"- Summary: {vulnerability['summary'] or 'No summary supplied by OSV.'}",
                    f"- Aliases: {', '.join(vulnerability['aliases']) or 'None supplied'}",
                    (
                        "- Fixed versions reported by OSV: "
                        f"{', '.join(vulnerability['fixed_versions']) or 'Not supplied'}"
                    ),
                    f"- Published: {vulnerability['published'] or 'Not supplied'}",
                    f"- Modified: {vulnerability['modified'] or 'Not supplied'}",
                ]
            )
            for url in vulnerability["references"]:
                lines.append(f"- Evidence URL: {url}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _normalize_vulnerability(vulnerability: dict[str, Any]) -> dict[str, Any]:
    advisory_id = str(vulnerability.get("id", ""))
    references = {
        f"https://osv.dev/vulnerability/{advisory_id}",
        *(
            str(reference.get("url", "")).strip()
            for reference in vulnerability.get("references", [])
            if isinstance(reference, dict) and reference.get("url")
        ),
    }
    return {
        "id": advisory_id,
        "aliases": _string_list(vulnerability.get("aliases")),
        "summary": str(vulnerability.get("summary", "")).strip(),
        "fixed_versions": _fixed_versions(vulnerability),
        "published": str(vulnerability.get("published", "")).strip(),
        "modified": str(vulnerability.get("modified", "")).strip(),
        "references": sorted(url for url in references if url),
    }


def _fetch_osv_vulnerability(advisory_id: str, *, timeout: float) -> dict[str, Any]:
    url = f"{OSV_VULNERABILITY_URL}{urllib.parse.quote(advisory_id, safe='')}"
    try:
        response = httpx.get(
            url,
            headers={"Accept": "application/json", "User-Agent": "K-LIB-Forge/1.0"},
            timeout=timeout,
        )
        response.raise_for_status()
        detail = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise KlibError(f"OSV advisory detail query failed for {advisory_id}: {exc}") from exc
    if not isinstance(detail, dict) or detail.get("id") != advisory_id:
        raise KlibError(f"OSV advisory detail response was invalid for {advisory_id}")
    return detail


def _fixed_versions(vulnerability: dict[str, Any]) -> list[str]:
    versions: set[str] = set()
    for affected in vulnerability.get("affected", []):
        if not isinstance(affected, dict):
            continue
        for range_data in affected.get("ranges", []):
            if not isinstance(range_data, dict):
                continue
            for event in range_data.get("events", []):
                if isinstance(event, dict) and event.get("fixed"):
                    versions.add(str(event["fixed"]))
    return sorted(versions)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _remove_previous_live_audits(manager: LibraryManager, library_id: str) -> None:
    for source in manager.sources(library_id):
        if source.get("title") == LIVE_SOURCE_TITLE:
            manager.delete_source(library_id, source["id"])
