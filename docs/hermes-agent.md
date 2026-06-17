# Hermes Agent Integration

Hermes Agent can use K-LIB Forge through the local `klib-mcp` stdio server.
This keeps K-LIB packages and indexes on the same machine while Hermes receives
only the MCP tools explicitly allowed in its configuration.

## Read-only setup

Install K-LIB Forge in a Python environment, then add the MCP server with the
Hermes CLI:

```powershell
hermes mcp add klib_forge `
  --command "D:\K-Lib Forge\.venv\Scripts\klib-mcp.exe" `
  --env "KLIB_HOME=$env:USERPROFILE\.klib-forge"
```

On the native Windows desktop build, the configuration is stored at
`%LOCALAPPDATA%\hermes\config.yaml`. Classic CLI installations commonly use
`~/.hermes/config.yaml`. Apply this read-only policy:

```yaml
mcp_servers:
  klib_forge:
    command: "D:\\K-Lib Forge\\.venv\\Scripts\\klib-mcp.exe"
    env:
      KLIB_HOME: "${USERPROFILE}\\.klib-forge"
    enabled: true
    timeout: 120
    connect_timeout: 60
    tools:
      include: [klib_list, klib_search]
      resources: false
      prompts: false
```

Start a new Hermes session or run `/reload-mcp`. Verify the connection with:

```powershell
hermes mcp test klib_forge
hermes mcp list
```

The tools appear as
`mcp_klib_forge_klib_list` and `mcp_klib_forge_klib_search`.

Example request:

```text
Search the biology-core-reference K-LIB for the sodium-potassium pump
stoichiometry. Answer only from retrieved evidence and cite the source title.
```

## MedChem Internet Discovery

For the MedChem workflow, use Hermes for discovery first, then K-LIB for
validation and repeatable packaging:

```powershell
$env:NVIDIA_API_KEY = "..."
.\.venv\Scripts\python.exe .\scripts\run-medchem-hermes-internet-klib.py `
  --compound Advil `
  --model minimaxai/minimax-m3 `
  --provider nvidia
```

The script asks Hermes + Minimax-M3 to use internet/web access only for the
discovery stage and return structured JSON. K-LIB then imports supported
PubChem identities, runs RDKit validation, detects duplicate InChIKey groups,
runs evidence checks, and produces a final MedChem research-agent report.

Use `--dry-run` to test the K-LIB side without calling Hermes or NVIDIA.

For B.AI:

```powershell
$env:BAI_API_KEY = "..."
.\.venv\Scripts\python.exe .\scripts\run-medchem-hermes-internet-klib.py `
  --compound Advil `
  --model minimax-m3 `
  --provider b-ai
```

This only works if Hermes also has a provider named `b-ai`. If Hermes uses a
different provider name, pass it with `--hermes-provider`.

If Hermes has a custom provider name such as `mimo`, pass it separately:

```powershell
.\.venv\Scripts\python.exe .\scripts\run-medchem-hermes-internet-klib.py `
  --compound Advil `
  --model mimo-v2.5-pro `
  --provider mimo `
  --hermes-provider mimo `
  --klib-provider hermes `
  --klib-model mimo-v2.5-pro
```

`--hermes-provider` is the provider name known to Hermes. `--klib-provider` is
the final synthesis route. Use `--klib-provider hermes` when you want K-LIB to
package the RDKit/evidence context and send the final answer prompt back through
the same Hermes provider.

## Broader access

`klib_compile` modifies local indexes. `klib_ask` sends the assembled prompt and
retrieved evidence to the model provider selected by the package or tool call.
Expose them only when that behavior is intended:

```yaml
tools:
  include: [klib_list, klib_search, klib_compile, klib_ask]
```

The K-LIB MCP allowlist does not restrict Hermes's other built-in tools. For a
knowledge-only agent, use a separate Hermes profile and disable filesystem,
terminal, GitHub, and coding tools independently.

## Compatibility check

K-LIB Forge 1.0.0 responds to MCP initialization and tool discovery using
protocol version `2025-03-26`. The local server exposes:

- `klib_list`
- `klib_search`
- `klib_compile`
- `klib_ask`

The read-only configuration above intentionally registers only `klib_list` and
`klib_search`. A successful end-to-end search should return evidence from
`02-membrane-transport.md` stating that the pump moves 3 Na+ out and 2 K+ in
for each ATP hydrolyzed.
