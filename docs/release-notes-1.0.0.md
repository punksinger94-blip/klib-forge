# K-LIB Forge 1.0.0

K-LIB Forge is a local-first system for compiling sources, rules, examples,
corrections, and deterministic evals into portable `.klib` knowledge packages.

## Highlights

- React and Tauri desktop application with a packaged local API sidecar
- CLI, FastAPI service, Python SDK, and MCP stdio server
- Advanced biomedical evidence-synthesis and production incident-response examples
- Native Anthropic Messages API support
- OpenAI-compatible connectors for major hosted and local model providers
- Arbitrary model IDs and custom OpenAI-compatible endpoints
- Local, Chroma, and Qdrant retrieval adapters
- Prompt-injection scanning, source trust controls, corrections, evals, and model arena
- Safe package import/export with schema and archive validation

## Qualification

- 36 Python tests passed with 86% coverage
- Python 3.12 and 3.14 clean-wheel qualification passed
- TypeScript production build passed
- Rust format, clippy, unit tests, doctests, and release build passed
- All 12 desktop views passed browser qualification without console errors
- Frozen API sidecar and NSIS install, launch, shutdown, and uninstall passed
- Python and npm dependency audits found no known vulnerabilities
- Release artifacts include SHA-256 checksums and Python, npm, and Rust metadata

The Windows installer is Authenticode-signed and timestamped before publication.
