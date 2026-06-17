# K-LIB Forge

Open-source, local-first build system for portable AI knowledge libraries.

K-LIB Forge turns documents, rules, glossaries, examples, corrections, and
evaluations into versioned `.klib` packages that can run with local or online
models.

**Build once. Run on any model.**

The built-in catalog includes primary-literature biomedical evidence synthesis
and production incident response. Browse it with `klib example-catalog` and
install a package with `klib install-example EXAMPLE_ID`.

## 1.0 capabilities

- Strict `.klib` package format with JSON Schema validation
- CLI, FastAPI service, React desktop UI, and Tauri native shell
- Self-contained Windows desktop installer with a packaged API sidecar
- Automatic backend startup, dynamic localhost port selection, and shutdown
- Advanced first-run examples with an offline model
- TXT, Markdown, PDF, JSON, and JSONL source ingestion
- Deterministic TF-IDF and local-vector retrieval, plus optional Chroma and Qdrant
- Hybrid lexical/vector score fusion
- Native Anthropic and broad OpenAI-compatible provider connectors
- Layered prompts with glossary, rules, examples, and retrieved evidence
- Suggested glossary terms, rules, examples, and evals
- Reviewed corrections that create regression evals
- Multi-model Eval Arena and Knowledge Diff snapshots
- Prompt-injection scanning and per-source trust levels
- Optional MedChem alpha with RDKit validation, descriptors, scaffolds, and similarity
- Package editors, model profiles, import/export, run history, and prompt inspection
- Stable Python SDK and MCP stdio server
- Safe ZIP-based `.klib` import and export
- SQLite registry and run history

The default indexes deliberately have no model download or hosted service
dependency. Chroma is an optional package extra; Qdrant connects to an explicitly
configured service.

## Quick start

Requires Python 3.11+ and Node.js 20+. Rust 1.91.1 is required only for native
desktop development.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements\dev-lock.txt
python -m pip install --no-deps -e .

klib init "My Knowledge Library" --domain research
Set-Location .\my-knowledge-library
klib add ..\docs
klib compile
klib search "important topic"
klib ask "Explain the important topic" --provider mock --model offline-demo
klib export ..\my-knowledge-library.klib
```

For CLI or browser development, start the API:

```powershell
klib-api
```

Start the desktop frontend in another terminal:

```powershell
Set-Location apps\desktop
npm ci
npm run dev
```

Run the native shell after installing Rust. This packages and starts the API
sidecar automatically:

```powershell
npm run tauri:dev
```

## Development

```powershell
.\scripts\bootstrap.ps1
.\scripts\build.ps1
```

The standalone API documentation is available at
`http://127.0.0.1:8000/docs` while `klib-api` is running. The packaged desktop
runtime uses a dynamically assigned localhost port.

The Windows installer is generated under:

```text
apps/desktop/src-tauri/target/release/bundle/nsis/
```

## NVIDIA biological A/B benchmark

The controlled benchmark compares:

- NVIDIA API key slot 1: the selected model with no K-LIB context
- NVIDIA API key slot 2: the same model, generation settings, and questions with
  the synthetic Vesperomyces biology K-LIB

Run it through the secure prompt wrapper:

```powershell
.\scripts\run-nvidia-biological-ab.ps1 `
  -Model "meta/llama-3.3-70b-instruct" `
  -Repeats 3 `
  -Crossover
```

The wrapper masks both new keys, keeps them in process memory only, and writes
the report under `build/experiments/`, which Git ignores. The crossover run
repeats the comparison with key assignments swapped to detect key-specific
routing or quota effects.

### Primary-literature biology benchmark

The literature benchmark uses five held-out questions backed by curated
evidence from primary studies in microbial RNA regulation, UPEC virulence,
marine small proteins, membrane biophysics, and single-cell protein modeling.
The baseline sees only each question. The K-LIB condition receives retrieved
study evidence with DOI and source provenance.

```powershell
.\scripts\run-nvidia-literature-biological-ab.ps1 `
  -Model "minimaxai/minimax-m3" `
  -Repeats 3 `
  -Crossover
```

This benchmark is literature-backed, but its answer key is not a substitute for
independent subject-matter-expert review. Large crossover runs can encounter
provider token-rate limits; the NVIDIA connector retries transient throttling,
and the wrapper preserves a `.log` beside the JSON report.

## Repository layout

```text
apps/desktop/                    React + Tauri IDE
services/api/                    FastAPI service
packages/klib-core/              Package, compiler, retrieval, eval, diff
packages/klib-cli/               Developer CLI
specs/klib-package-spec/         Open JSON Schemas
examples/                        Example knowledge packages
docs/                            Architecture and user guides
tests/                           End-to-end core and API tests
```

## Model privacy

New packages default to local-only model use. Online providers are rejected
until `model_policy.allow_online_models` is enabled in `manifest.json`.
K-LIB Forge has no telemetry. See [Privacy and Data](docs/privacy.md).

## Model providers

Run `klib models` for the live connector catalog. Named connectors cover
OpenAI, Azure OpenAI, Anthropic, NVIDIA NIM, Gemini, Groq, xAI, Mistral,
OpenRouter, DeepSeek, Together, Fireworks, Perplexity, Cerebras, SambaNova,
Amazon Bedrock Mantle, Ollama, LM Studio, vLLM, llama.cpp, and text generation
web UI. Model IDs are passed through without an allowlist, so newly released
models do not require a K-LIB Forge update.

For any other text-chat service, select `openai-compatible`, set its base URL,
and provide an API key when required. Vendor-specific image, audio, tool, and
batch APIs are outside this connector surface.

## Documentation

- [Installation and removal](docs/installation.md)
- [Getting started](docs/getting-started.md)
- [Architecture](docs/architecture.md)
- [SDK and MCP](docs/sdk-and-mcp.md)
- [Hermes Agent integration](docs/hermes-agent.md)
- [Biology private-knowledge demo](docs/biology-private-knowledge-demo.md)
- [MedChem-KLIB Lite](docs/medchem-lite.md)
- [Private Anthropic knowledge collection](docs/anthropic-knowledge-collection.md)
- [Known limitations](docs/known-limitations.md)
- [Release process](docs/release.md)
- [1.0.0 release qualification](docs/release-qualification-1.0.0.md)
- [Security policy](SECURITY.md)

Run `.\scripts\release-doctor.ps1` to validate a local release candidate. Add
`-Public` to require a reachable GitHub origin and a trusted Windows signature.

## License

K-LIB Forge is licensed under Apache-2.0. Knowledge packages can declare their
own content license in `manifest.json`.
