from __future__ import annotations

from pathlib import Path

import httpx
from klib_core import ForgeEngine, LibraryManager
from klib_core.dependency_security import (
    LIVE_SOURCE_TITLE,
    build_osv_report,
    parse_pinned_requirements,
    refresh_osv_evidence,
)
from klib_core.examples import install_builtin_example, list_builtin_examples


def test_dependency_security_example_installs_and_runs_evals(tmp_path: Path) -> None:
    manager = LibraryManager(tmp_path / "home")
    created, library_path = install_builtin_example(manager, "dependency-security-intelligence")

    assert created is True
    manifest, resolved_path = manager.get("dependency-security-intelligence")
    assert resolved_path == library_path
    assert manifest.model_policy.allow_online_models is True
    assert manifest.model_policy.default_provider == "ollama"
    assert len(manager.sources(manifest.id)) == 4

    results = ForgeEngine(manager).run_evals(manifest.id, provider="mock", model="offline-demo")
    assert len(results) == 3
    assert all(result.score == 100 for result in results)


def test_live_osv_refresh_replaces_previous_report(tmp_path: Path, monkeypatch) -> None:
    manager = LibraryManager(tmp_path / "home")
    install_builtin_example(manager, "dependency-security-intelligence")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pypdf==6.13.2\n# comment\npypdf==6.13.2\n", encoding="utf-8")

    observed_payloads: list[dict] = []

    def fake_post(url: str, **kwargs) -> httpx.Response:
        assert url == "https://api.osv.dev/v1/querybatch"
        observed_payloads.append(kwargs["json"])
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "results": [
                    {
                        "vulns": [
                            {
                                "id": "GHSA-jm82-fx9c-mx94",
                                "aliases": ["CVE-2026-00001"],
                                "summary": "Regression advisory fixture.",
                                "affected": [
                                    {
                                        "ranges": [
                                            {
                                                "type": "ECOSYSTEM",
                                                "events": [
                                                    {"introduced": "0"},
                                                    {"fixed": "6.13.3"},
                                                ],
                                            }
                                        ]
                                    }
                                ],
                                "references": [
                                    {
                                        "type": "ADVISORY",
                                        "url": "https://github.com/advisories/GHSA-jm82-fx9c-mx94",
                                    }
                                ],
                            }
                        ]
                    }
                ]
            },
        )

    def fake_get(url: str, **_kwargs) -> httpx.Response:
        assert url == "https://api.osv.dev/v1/vulns/GHSA-jm82-fx9c-mx94"
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={
                "id": "GHSA-jm82-fx9c-mx94",
                "aliases": ["CVE-2026-00001"],
                "summary": "Regression advisory fixture.",
                "affected": [
                    {
                        "ranges": [
                            {
                                "type": "ECOSYSTEM",
                                "events": [{"introduced": "0"}, {"fixed": "6.13.3"}],
                            }
                        ]
                    }
                ],
                "references": [
                    {
                        "type": "ADVISORY",
                        "url": "https://github.com/advisories/GHSA-jm82-fx9c-mx94",
                    }
                ],
            },
        )

    monkeypatch.setattr("klib_core.dependency_security.httpx.post", fake_post)
    monkeypatch.setattr("klib_core.dependency_security.httpx.get", fake_get)
    first = refresh_osv_evidence(manager, "dependency-security-intelligence", requirements)
    second = refresh_osv_evidence(manager, "dependency-security-intelligence", requirements)

    assert observed_payloads == [
        {
            "queries": [
                {
                    "package": {"name": "pypdf", "ecosystem": "PyPI"},
                    "version": "6.13.2",
                }
            ]
        }
    ] * 2
    assert first["report"]["matched_dependency_count"] == 1
    assert second["source"]["title"] == LIVE_SOURCE_TITLE
    assert second["source"]["trust_level"] == "trusted"
    live_source_path = (
        manager.get("dependency-security-intelligence")[1] / second["source"]["path"]
    )
    assert "6.13.3" in live_source_path.read_text(encoding="utf-8")
    live_sources = [
        item
        for item in manager.sources("dependency-security-intelligence")
        if item["title"] == LIVE_SOURCE_TITLE
    ]
    assert len(live_sources) == 1


def test_dependency_parser_and_report_preserve_uncertainty(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "# lock file\nfoo_bar==1.2.3 ; python_version >= '3.11'\ninvalid>=2\n",
        encoding="utf-8",
    )

    dependencies = parse_pinned_requirements(requirements)
    report = build_osv_report(dependencies, [{}])

    assert dependencies == [{"name": "foo-bar", "version": "1.2.3", "ecosystem": "PyPI"}]
    assert report["findings"][0]["status"] == "no_match_returned"
    assert any(item["id"] == "dependency-security-intelligence" for item in list_builtin_examples())
