from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .sdk import KlibRuntime
from .version import __version__

SERVER_INFO = {"name": "klib-forge", "version": __version__}

TOOLS = [
    {
        "name": "klib_list",
        "description": "List registered local K-LIB packages.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "klib_search",
        "description": "Search compiled evidence in a K-LIB package.",
        "inputSchema": {
            "type": "object",
            "required": ["library", "query"],
            "properties": {
                "library": {"type": "string"},
                "query": {"type": "string"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 50},
            },
        },
    },
    {
        "name": "klib_compile",
        "description": "Compile a K-LIB package and rebuild its indexes.",
        "inputSchema": {
            "type": "object",
            "required": ["library"],
            "properties": {"library": {"type": "string"}},
        },
    },
    {
        "name": "klib_ask",
        "description": "Ask a model with K-LIB policy and retrieved evidence.",
        "inputSchema": {
            "type": "object",
            "required": ["library", "prompt"],
            "properties": {
                "library": {"type": "string"},
                "prompt": {"type": "string"},
                "provider": {"type": "string"},
                "model": {"type": "string"},
                "base_url": {"type": "string"},
            },
        },
    },
]


def run() -> None:
    home = Path(value) if (value := __import__("os").getenv("KLIB_HOME")) else None
    runtime = KlibRuntime(home)
    for line in sys.stdin:
        if not line.strip():
            continue
        response = _handle_line(line, runtime)
        if response is None:
            continue
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _handle_line(
    line: str,
    runtime_or_home: KlibRuntime | Path | None = None,
) -> dict[str, Any] | None:
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        return _error(None, -32700, f"Parse error: {exc.msg}")
    if not isinstance(request, dict):
        return _error(None, -32600, "Invalid Request")
    runtime = (
        runtime_or_home
        if isinstance(runtime_or_home, KlibRuntime)
        else KlibRuntime(runtime_or_home)
    )
    try:
        return _handle(runtime, request)
    except Exception as exc:
        return _error(request.get("id"), -32603, str(exc))


def _handle(runtime: KlibRuntime, request: dict[str, Any]) -> dict[str, Any] | None:
    if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
        return _error(request.get("id"), -32600, "Invalid Request")
    method = request.get("method")
    request_id = request.get("id")
    is_notification = "id" not in request
    if method == "initialize":
        result = {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
    elif method == "notifications/initialized":
        return None
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params", {})
        if not isinstance(params, dict):
            return _error(request_id, -32602, "Invalid params")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            return _error(request_id, -32602, "Invalid params")
        try:
            value = _call_tool(runtime, str(params.get("name", "")), arguments)
            text = json.dumps(value, ensure_ascii=False, indent=2)
            is_error = False
        except Exception as exc:
            text = str(exc)
            is_error = True
        result = {
            "content": [{"type": "text", "text": text}],
            "isError": is_error,
        }
    else:
        return None if is_notification else _error(
            request_id,
            -32601,
            f"Method not found: {method}",
        )
    if is_notification:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _call_tool(runtime: KlibRuntime, name: str, arguments: dict[str, Any]) -> Any:
    if name == "klib_list":
        return runtime.libraries()
    if name == "klib_search":
        return runtime.search(
            arguments["library"],
            arguments["query"],
            top_k=arguments.get("top_k"),
        )
    if name == "klib_compile":
        return runtime.compile(arguments["library"])
    if name == "klib_ask":
        configuration = {
            key: arguments[key]
            for key in ("provider", "model", "base_url")
            if arguments.get(key)
        }
        return runtime.ask(arguments["library"], arguments["prompt"], **configuration)
    raise ValueError(f"Unknown tool: {name}")


if __name__ == "__main__":
    run()
