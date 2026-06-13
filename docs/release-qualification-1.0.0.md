# K-LIB Forge 1.0.0 Release Qualification

Qualification date: 2026-06-13

## Decision

The 1.0.0 local release candidate passed deep functional, security, packaging,
browser, and native installer qualification. It is ready for signing and public
release automation.

Public publication remains blocked until:

- the Windows installer is Authenticode-signed;
- a canonical GitHub `origin` is configured and reachable;
- the `v1.0.0` tag is created and pushed.

## Automated Gates

| Gate | Result |
| --- | --- |
| Ruff | Pass |
| Python tests | 36 passed |
| Python coverage | 86% |
| TypeScript and Vite production build | Pass |
| Rust format, clippy, tests, and locked build | Pass |
| Python runtime and development dependency audits | No known vulnerabilities |
| npm production and full dependency audits | No known vulnerabilities |
| RustSec audit | No vulnerabilities; 17 allowed transitive warnings |
| Schema parity and Draft 2020-12 validation | Pass |
| Repository and experiment secret scans | Pass |
| Wheel and sdist metadata validation | Pass |

## Installed Artifact Tests

- The wheel installed and imported successfully in clean Python 3.12 and 3.14
  virtual environments; `pip check` passed in both.
- The installed CLI completed create, add, compile, search, glossary, rule,
  example, export, import, rebuild, and search round trips.
- The installed MCP executable completed initialize, notification, tool list,
  and search calls over stdio JSON-RPC.
- The installed API exposed the complete provider and example catalogs,
  installed the production incident package, and completed a grounded mock ask.
- The frozen PyInstaller sidecar completed health, capability detection,
  provider-catalog, and example-catalog checks.
- The NSIS artifact completed silent install, desktop launch, dynamic managed
  backend startup, graceful shutdown with backend cleanup, and silent uninstall
  with no files left behind.

Installer SHA-256:
`035e65272b7b5a6e29d955d23df0aec380587dd3433cf22650bc55b94de6c7a5`.

## Desktop Browser Tests

All 12 desktop views rendered without console errors after fixes:

Dashboard, Sources, Glossary, Rules, Examples, Suggestions, Corrections,
Playground, Eval Arena, Run History, Knowledge Diff, and Settings.

Browser interactions covered the advanced biomedical example installation,
five-source retrieval, mock generation, dynamic provider catalogs in Playground
and Eval Arena, provider settings, and a final all-view sweep.

## Provider Compatibility

- 23 named connector profiles are exposed consistently in the core, CLI, API,
  and desktop.
- Anthropic uses its native Messages API request and response contract.
- OpenAI, Azure OpenAI, NVIDIA NIM, Gemini, Groq, xAI, Mistral, OpenRouter,
  DeepSeek, Together, Fireworks, Perplexity, Cerebras, SambaNova, Amazon
  Bedrock Mantle, and major local runtimes use OpenAI-compatible text-chat
  transport.
- `openai-compatible` accepts arbitrary base URLs for additional providers.
- Model identifiers are passed through without an allowlist, so new text-chat
  models do not require a K-LIB Forge release.

This surface does not claim vendor-specific image, audio, tool, or batch API
compatibility.

## Built-in Examples

- Biomedical Evidence Synthesis: five curated primary studies and five
  citation-aware quantitative evals.
- Production Incident Response: three operational sources and three
  evidence-preserving incident evals.

The former Arabic technical translation demo and endpoint were removed.

## NVIDIA MiniMax M3 Tests

Real NVIDIA API tests used separate baseline and K-LIB key slots with crossover:

| Benchmark | Baseline | K-LIB | Rows |
| --- | ---: | ---: | ---: |
| Synthetic Vesperomyces, assignment A/B | 0.0 | 100.0 | 12 |
| Synthetic Vesperomyces, assignment B/A | 0.0 | 100.0 | 12 |
| Primary literature, assignment A/B | 8.0 | 100.0 | 5 |
| Primary literature, assignment B/A | 4.0 | 100.0 | 5 |

Model: `minimaxai/minimax-m3`. Generation used temperature 0 and a 1024-token
limit. Reports remain under ignored `build/experiments/`; no credential values
are stored in them.

## Defects Corrected

- Package imports now reconstruct source registry rows and compile correctly.
- Compile failures preserve the previous database and local indexes.
- Archive import enforces path, symlink, encryption, count, and size limits.
- Eval identifiers and payloads are schema-validated.
- Duplicate library IDs and unsafe managed deletion are rejected safely.
- Chunk bounds, retry delays, API validation, and status codes are hardened.
- MCP notifications, parse failures, and tool errors follow protocol behavior.
- Qdrant rebuilds remove stale points and adapter failures are normalized.
- The desktop detects unavailable optional adapters.
- Eval counts and same-model arena rendering remain consistent.
- Release SBOM metadata is emitted and validated as portable UTF-8 JSON.
- Provider definitions now come from one registry shared by every interface.
- Advanced examples now come from one idempotent install catalog.

## Residual Risk

- Python 3.11 is covered by CI configuration but was not installed on this
  workstation for the artifact smoke test.
- Chroma requires `klib-forge[chroma]` and is not bundled in the Windows
  desktop runtime.
- Qdrant requires an external service; its HTTP contract and failure behavior
  were tested without a live local Qdrant instance.
- The unsigned local installer is a candidate artifact only.
- The workstation has no publicly trusted code-signing certificate; the only
  available private-key certificate is an untrusted test-driver certificate
  and was deliberately not used.
- GitHub CLI is not installed/authenticated, no canonical `origin` exists, and
  no repository is currently available under `punksinger94-blip` through the
  connected GitHub integration.
