from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

import httpx

from .errors import ModelProviderError


@dataclass(frozen=True)
class ProviderSpec:
    provider: str
    name: str
    transport: str
    default_base_url: str | None
    api_key_env: str | None
    local: bool = False
    api_key_required: bool = True
    base_url_required: bool = False

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


PROVIDER_SPECS = (
    ProviderSpec("mock", "Offline demo", "mock", None, None, local=True, api_key_required=False),
    ProviderSpec(
        "ollama", "Ollama", "openai", "http://localhost:11434/v1", None,
        local=True, api_key_required=False,
    ),
    ProviderSpec(
        "lmstudio", "LM Studio", "openai", "http://localhost:1234/v1", None,
        local=True, api_key_required=False,
    ),
    ProviderSpec(
        "vllm", "vLLM", "openai", "http://localhost:8000/v1", None,
        local=True, api_key_required=False,
    ),
    ProviderSpec(
        "llamacpp", "llama.cpp", "openai", "http://localhost:8080/v1", None,
        local=True, api_key_required=False,
    ),
    ProviderSpec(
        "text-generation-webui",
        "Text generation web UI",
        "openai",
        "http://localhost:5000/v1",
        None,
        local=True,
        api_key_required=False,
    ),
    ProviderSpec(
        "openai", "OpenAI", "openai", "https://api.openai.com/v1", "OPENAI_API_KEY"
    ),
    ProviderSpec(
        "azure-openai", "Azure OpenAI", "openai", None, "AZURE_OPENAI_API_KEY",
        base_url_required=True,
    ),
    ProviderSpec(
        "anthropic", "Anthropic", "anthropic", "https://api.anthropic.com",
        "ANTHROPIC_API_KEY",
    ),
    ProviderSpec(
        "nvidia", "NVIDIA NIM", "openai", "https://integrate.api.nvidia.com/v1",
        "NVIDIA_API_KEY",
    ),
    ProviderSpec(
        "b-ai", "B.AI", "openai", "https://api.b.ai/v1", "BAI_API_KEY",
    ),
    ProviderSpec(
        "gemini", "Google Gemini", "openai",
        "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY",
    ),
    ProviderSpec(
        "groq", "Groq", "openai", "https://api.groq.com/openai/v1", "GROQ_API_KEY"
    ),
    ProviderSpec("xai", "xAI", "openai", "https://api.x.ai/v1", "XAI_API_KEY"),
    ProviderSpec(
        "mistral", "Mistral AI", "openai", "https://api.mistral.ai/v1", "MISTRAL_API_KEY"
    ),
    ProviderSpec(
        "openrouter", "OpenRouter", "openai", "https://openrouter.ai/api/v1",
        "OPENROUTER_API_KEY",
    ),
    ProviderSpec(
        "deepseek", "DeepSeek", "openai", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"
    ),
    ProviderSpec(
        "together", "Together AI", "openai", "https://api.together.ai/v1",
        "TOGETHER_API_KEY",
    ),
    ProviderSpec(
        "fireworks", "Fireworks AI", "openai",
        "https://api.fireworks.ai/inference/v1", "FIREWORKS_API_KEY",
    ),
    ProviderSpec(
        "perplexity", "Perplexity", "openai", "https://api.perplexity.ai",
        "PERPLEXITY_API_KEY",
    ),
    ProviderSpec(
        "cerebras", "Cerebras", "openai", "https://api.cerebras.ai/v1",
        "CEREBRAS_API_KEY",
    ),
    ProviderSpec(
        "sambanova", "SambaNova", "openai", "https://api.sambanova.ai/v1",
        "SAMBANOVA_API_KEY",
    ),
    ProviderSpec(
        "bedrock", "Amazon Bedrock Mantle", "openai", None,
        "AWS_BEARER_TOKEN_BEDROCK", base_url_required=True,
    ),
    ProviderSpec(
        "openai-compatible",
        "Custom OpenAI-compatible endpoint",
        "openai",
        None,
        "OPENAI_API_KEY",
        api_key_required=False,
        base_url_required=True,
    ),
)

_PROVIDER_INDEX = {item.provider: item for item in PROVIDER_SPECS}


def provider_specs() -> list[dict[str, Any]]:
    return [item.model_dump() for item in PROVIDER_SPECS]


def is_local_provider(provider: str) -> bool:
    spec = _PROVIDER_INDEX.get(provider.casefold())
    return bool(spec and spec.local)


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


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after")
    try:
        if retry_after:
            return max(0, min(float(retry_after), 120))
    except ValueError:
        pass
    return min(15 * (2**attempt), 120) if response.status_code == 429 else 2**attempt


def _post_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            retryable = status in {408, 429} or status >= 500
            if retryable and attempt < max_attempts - 1:
                time.sleep(_retry_delay(exc.response, attempt))
                continue
            raise ModelProviderError(f"Model request failed: HTTP {status}") from exc
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if attempt < max_attempts - 1:
                time.sleep(2**attempt)
                continue
            raise ModelProviderError(f"Model request failed: {exc}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ModelProviderError(f"Model request failed: {exc}") from exc
    raise ModelProviderError("Model request failed after retries")


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
        try:
            data = _post_json(
                f"{self.base_url}/chat/completions",
                headers=headers,
                payload=payload,
                timeout=self.timeout,
            )
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelProviderError(f"Model response was not OpenAI-compatible: {exc}") from exc


class AnthropicProvider(ModelProvider):
    def __init__(self, base_url: str, api_key: str, timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def chat(self, messages: list[dict[str, str]], model: str, options: dict[str, Any]) -> str:
        system_parts = [item["content"] for item in messages if item["role"] == "system"]
        anthropic_messages = [
            item for item in messages if item["role"] in {"user", "assistant"}
        ]
        payload: dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": options.get("max_tokens", 4096),
            "temperature": options.get("temperature", 0.2),
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        for option in ("stop_sequences", "top_k", "top_p"):
            if option in options:
                payload[option] = options[option]
        if isinstance(options.get("extra_body"), dict):
            payload.update(options["extra_body"])
        data = _post_json(
            f"{self.base_url}/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": str(options.get("anthropic_version", "2023-06-01")),
            },
            payload=payload,
            timeout=self.timeout,
        )
        try:
            return "".join(
                str(block["text"])
                for block in data["content"]
                if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise ModelProviderError(f"Model response was not Anthropic-compatible: {exc}") from exc


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
    spec = _PROVIDER_INDEX.get(normalized)
    if not spec:
        raise ModelProviderError(
            f"Unknown provider: {provider}. Use openai-compatible for a custom endpoint."
        )
    if spec.transport == "mock":
        return MockProvider()

    resolved_url = base_url or (
        os.getenv("OPENAI_BASE_URL") if normalized == "openai-compatible" else None
    ) or spec.default_base_url
    if not resolved_url:
        raise ModelProviderError(f"A base URL is required for the {normalized} provider")

    resolved_key = api_key or (os.getenv(spec.api_key_env) if spec.api_key_env else None)
    if spec.api_key_required and not resolved_key:
        raise ModelProviderError(f"{spec.api_key_env} is required for the {normalized} provider")
    if spec.transport == "anthropic":
        return AnthropicProvider(resolved_url, resolved_key or "")
    return OpenAICompatibleProvider(resolved_url, resolved_key)
