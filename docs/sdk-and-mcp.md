# SDK and MCP

## Python SDK

```python
from klib_core import KlibRuntime

runtime = KlibRuntime()
runtime.compile("my-library")
results = runtime.search("my-library", "configuration", top_k=5)
answer = runtime.ask("my-library", "Explain the configuration", provider="mock")
```

`KlibApiClient` provides the same common operations against a running FastAPI service.

## MCP server

Run the stdio server with:

```powershell
klib-mcp
```

It exposes `klib_list`, `klib_search`, `klib_compile`, and `klib_ask`. The MCP
process uses `KLIB_HOME` when set and otherwise uses the normal local K-LIB home.
