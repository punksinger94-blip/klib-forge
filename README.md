# K-LIB Forge

Open-source, local-first build system for portable AI knowledge libraries.

K-LIB Forge turns documents, rules, glossaries, examples, corrections, and
evaluations into versioned `.klib` packages that can run with local or online
models.

**Build once. Run on any model.**

## Vision: a knowledge compiler, not just RAG

K-LIB Forge is built around a compiler-style idea: knowledge should be checked
before a model uses it. Retrieval-augmented generation usually decides what
context to trust at inference time, once per query. K-LIB packages move more of
that work to build time, where sources, rules, examples, corrections, evals,
and domain records can be inspected, validated, versioned, and shipped as one
portable artifact.

The goal is not to replace retrieval. The goal is to make retrieval run over a
known, testable package instead of a loose folder of documents.

| Question | Typical RAG stack | K-LIB Forge direction |
| --- | --- | --- |
| When is knowledge checked? | At inference time | At package build time and again in evals |
| What is the output? | Prompt context for one run | A versioned `.klib` package |
| What can be audited? | Usually the final answer and retrieved chunks | Sources, package manifest, rules, evals, reports, and run history |
| How are fixes kept? | Often as prompt changes | Corrections can become regression evals |
| Model coupling | Usually tied to one provider or vector store | Package can run with local or hosted models |

In the long-term version of K-LIB Forge, a package build should feel like a
compiler pass: parse records, validate structure, check references, attach
provenance, enforce safety boundaries, run evals, and emit diagnostics when a
record is not shippable.

## Preview 2 reality

Preview 2 already implements the practical core of that model:

- `.klib` import/export with safe ZIP handling and JSON Schema validation
- CLI, FastAPI service, desktop UI, Python SDK, and MCP server
- deterministic compile and eval flows for package regression checks
- reviewed corrections that can create regression evals
- package run history, prompt inspection, Eval Arena, and Knowledge Diff UI
- local-first retrieval with optional vector backends
- broad local and hosted model connector support
- MedChem-KLIB Lite with RDKit validation, descriptors, scaffolds, similarity
  search, duplicate identity review, evidence links, safety checks, and
  research-only boundaries
- desktop installer that starts its bundled API sidecar and bootstraps
  MedChem-KLIB Lite into the local runtime

The current MedChem workflow is the clearest compiler-style example: invalid
molecular records are rejected, compiled compounds keep RDKit-derived
descriptors and provenance labels, linked evidence can be summarized with
citations, and safety probes are tested as part of the evidence regression
suite.

Example Preview 2 flow:

```powershell
klib install-example medchem-lite
klib medchem validate --library medchem-lite
klib medchem compile --library medchem-lite
klib medchem similar "CC(=O)Oc1ccccc1C(=O)O" --library medchem-lite
klib medchem evidence-evals --library medchem-lite
klib export medchem-lite.klib --library medchem-lite
```

## Roadmap

The compiler vision is not finished. The next important steps are:

- a typed knowledge IR so package records can be checked more like typed data
- stronger semantic provenance checks that verify cited values against source
  spans, not just source links
- domain-pluggable validators beyond chemistry, such as biology unit,
  ontology, sequence, and identifier checks
- richer Knowledge Diff semantics between two compiled package snapshots
- cleaner release signing with a publicly trusted Authenticode certificate
- deeper installer and first-run tests across clean Windows environments

K-LIB Forge is still a pre-release. Expect package format and workflow changes
before a stable 1.0 line.

## Current preview release

The latest preview is
[K-LIB Forge 1.0.0 Preview 2](https://github.com/punksinger94-blip/klib-forge/releases/tag/v1.0.0-preview.2).

Preview 2 includes the MedChem-KLIB Lite workflow, Hermes Agent integration
guides, the biology reference package, and a new deep release qualification
gate. The final pre-release qualification report passed **8/8** gates: Python
lint, pytest, desktop UI build, CLI, API, MCP, ecosystem smoke, and the advanced
Advil/ibuprofen MedChem research workflow.

The Windows installer is SignPath-processed, timestamped, and MedChem-enabled,
but the signing certificate is not publicly trusted yet. Windows may still show
a trust warning; treat this as a preview build until a publicly trusted
Authenticode certificate is configured.

The built-in catalog includes primary-literature biomedical evidence synthesis,
production incident response, and MedChem-KLIB Lite. Browse it with
`klib example-catalog` and install a package with:

```powershell
klib install-example EXAMPLE_ID
```

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
- MedChem-KLIB Lite with RDKit validation, descriptors, scaffolds, similarity,
  duplicate identity review, source roadmap, and 2D/3D visualization hooks
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

Release assets for Preview 2 are published on GitHub and include the Windows
installer, Python wheel, source distribution, demo video, signing notice,
SHA256 hashes, release-readiness report, and deep qualification report.

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
