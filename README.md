# K-LIB Forge

Open-source, local-first build system for portable AI knowledge libraries.

K-LIB Forge turns documents, rules, glossaries, examples, corrections, and
evaluations into versioned `.klib` packages that can run with local or online
models.

**Build once. Run on any model.**

## v0.1.1 capabilities

- Strict `.klib` package format with JSON Schema validation
- CLI, FastAPI service, React desktop UI, and Tauri native shell
- Self-contained Windows desktop installer with a packaged API sidecar
- Automatic backend startup, dynamic localhost port selection, and shutdown
- First-run ready-to-use example with an offline model
- TXT, Markdown, PDF, JSON, and JSONL source ingestion
- Deterministic local chunking, keyword extraction, and TF-IDF retrieval
- Ollama, LM Studio, OpenAI, OpenAI-compatible, and offline mock connectors
- Layered prompts with glossary, rules, examples, and retrieved evidence
- Corrections that can create regression evals
- Basic eval runner and Knowledge Diff snapshots
- Safe ZIP-based `.klib` import and export
- SQLite registry and run history

The default local index deliberately has no model download or hosted service
dependency. Chroma is available as an optional package extra and is planned as
an interchangeable vector adapter after the v0.1 package contract stabilizes.

## Quick start

Requires Python 3.11+ and Node.js 20+. Rust 1.77.2+ is required only for the
native Tauri executable.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

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
npm install
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

## License

K-LIB Forge is licensed under Apache-2.0. Knowledge packages can declare their
own content license in `manifest.json`.
