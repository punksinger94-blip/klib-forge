from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from .engine import ForgeEngine
from .library import LibraryManager


class KlibRuntime:
    """Stable in-process SDK for package management, retrieval, and model runs."""

    def __init__(self, home: Path | None = None):
        self.manager = LibraryManager(home)
        self.engine = ForgeEngine(self.manager)

    def libraries(self) -> list[dict[str, Any]]:
        return self.manager.list()

    def compile(self, library: str | Path) -> dict[str, Any]:
        return self.engine.compile(library).model_dump(mode="json")

    def search(
        self,
        library: str | Path,
        query: str,
        *,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        return [
            item.model_dump(mode="json")
            for item in self.engine.search(library, query, top_k)
        ]

    def ask(
        self,
        library: str | Path,
        prompt: str,
        **options: Any,
    ) -> dict[str, Any]:
        return self.engine.ask(library, prompt, **options).model_dump(mode="json")


class KlibApiClient:
    """Small typed HTTP client for a running K-LIB Forge API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def libraries(self) -> list[dict[str, Any]]:
        return self._request("GET", "/libraries")

    def library(self, library_id: str) -> dict[str, Any]:
        return self._request("GET", f"/libraries/{library_id}")

    def search(self, library_id: str, query: str, top_k: int = 8) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            f"/libraries/{library_id}/search",
            params={"q": query, "top_k": top_k},
        )

    def ask(self, library_id: str, prompt: str, **configuration: Any) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/libraries/{library_id}/ask",
            json={"input": prompt, **configuration},
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = httpx.request(
            method,
            f"{self.base_url}{path}",
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()
