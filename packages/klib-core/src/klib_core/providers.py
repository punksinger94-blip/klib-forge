from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from .errors import ModelProviderError


class ModelProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict[str, str]], model: str, options: dict[str, Any]) -> str:
        raise NotImplementedError

    def test(self, model: str) -> dict[str, Any]:
        output = self.chat(
            [{"role": "user", "content": "Reply with exactly: K-LIB OK"}],
            model,
            {"temperature": 0},
        )
        return {"ok": bool(output.strip()), "output": output}


class OpenAICompatibleProvider(ModelProvider):
    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def chat(self, messages: list[dict[str, str]], model: str, options: dict[str, Any]) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": options.get("temperature", 0.2),
        }
        for option in (
            "frequency_penalty",
            "max_tokens",
            "presence_penalty",
            "seed",
            "stop",
            "top_p",
        ):
            if option in options:
                payload[option] = options[option]
        if isinstance(options.get("extra_body"), dict):
            payload.update(options["extra_body"])
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                return str(data["choices"][0]["message"]["content"])
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                retryable = status in {408, 429} or status >= 500
                if retryable and attempt < max_attempts - 1:
                    retry_after = exc.response.headers.get("retry-after")
                    try:
                        if retry_after:
                            delay = max(0, min(float(retry_after), 120))
                        elif status == 429:
                            delay = min(15 * (2**attempt), 120)
                        else:
                            delay = 2**attempt
                    except ValueError:
                        delay = 15 if status == 429 else 2**attempt
                    time.sleep(delay)
                    continue
                raise ModelProviderError(f"Model request failed: HTTP {status}") from exc
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < max_attempts - 1:
                    time.sleep(2**attempt)
                    continue
                raise ModelProviderError(f"Model request failed: {exc}") from exc
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                raise ModelProviderError(f"Model request failed: {exc}") from exc
        raise ModelProviderError("Model request failed after retries")


class MockProvider(ModelProvider):
    """Offline provider for demos and automated tests."""

    def chat(self, messages: list[dict[str, str]], model: str, options: dict[str, Any]) -> str:
        prompt = messages[-1]["content"]
        knowledge = prompt.split("Glossary:", 1)[-1] if "Glossary:" in prompt else prompt
        knowledge = knowledge.split("User request:", 1)[0].strip()
        if knowledge:
            return f"Offline demo answer based on the selected K-LIB:\n{knowledge[:1200]}"
        return (
            "Offline demo provider is connected. "
            "Compile and add matching sources for grounded output."
        )


def get_provider(
    provider: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> ModelProvider:
    normalized = provider.casefold()
    if normalized == "mock":
        return MockProvider()
    if normalized == "ollama":
        return OpenAICompatibleProvider(base_url or "http://localhost:11434/v1", api_key="ollama")
    if normalized in {"nvidia", "openai", "openai-compatible", "lmstudio"}:
        default_url = {
            "nvidia": "https://integrate.api.nvidia.com/v1",
            "openai": "https://api.openai.com/v1",
            "openai-compatible": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "lmstudio": "http://localhost:1234/v1",
        }[normalized]
        environment_key = {
            "nvidia": "NVIDIA_API_KEY",
            "openai": "OPENAI_API_KEY",
            "openai-compatible": "OPENAI_API_KEY",
            "lmstudio": "OPENAI_API_KEY",
        }[normalized]
        resolved_key = api_key or os.getenv(environment_key)
        if normalized in {"nvidia", "openai"} and not resolved_key:
            raise ModelProviderError(
                f"{environment_key} is required for the {normalized} provider"
            )
        return OpenAICompatibleProvider(base_url or default_url, resolved_key or "local")
    raise ModelProviderError(f"Unknown provider: {provider}")
