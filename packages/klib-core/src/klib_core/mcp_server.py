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
    runtime = KlibRuntime(
        Path(home) if (home := __import__("os").getenv("KLIB_HOME")) else None
    )
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = _handle(runtime, request)
        except Exception as exc:
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id") if "request" in locals() else None,
                "error": {"code": -32603, "message": str(exc)},
            }
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _handle(runtime: KlibRuntime, request: dict[str, Any]) -> dict[str, Any]:
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        result = {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
    elif method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params", {})
        value = _call_tool(runtime, params.get("name", ""), params.get("arguments", {}))
        result = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(value, ensure_ascii=False, indent=2),
                }
            ],
            "isError": False,
        }
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


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
