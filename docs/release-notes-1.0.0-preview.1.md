# K-LIB Forge 1.0.0 Preview 1

This is an early-access GitHub pre-release for installation and workflow
testing. It is not the final trusted 1.0.0 release.

## Important Signing Notice

The Windows installer is Authenticode-signed and timestamped through SignPath,
but the signing certificate is the project's self-signed test certificate
`CN=klib`. Windows will report an unknown or untrusted publisher. The signature
protects artifact integrity but does not establish public publisher trust.

Install this preview only when downloaded from this GitHub release and after
verifying `SHA256SUMS.txt`. The final stable release will use a publicly trusted
code-signing certificate.

## Included

- React and Tauri desktop application with packaged local API sidecar
- CLI, FastAPI service, Python SDK, and MCP stdio server
- Biomedical evidence-synthesis and production incident-response examples
- Native Anthropic and OpenAI-compatible provider transports
- Arbitrary model IDs and custom OpenAI-compatible endpoints
- Local, Chroma, and Qdrant retrieval adapters
- Prompt-injection scanning, source trust controls, corrections, and eval arena

## Qualification

- 36 Python tests passed with 86% coverage
- Python 3.11 and 3.12 hosted CI passed
- TypeScript build and npm audit passed
- Rust format, clippy, tests, and audit passed
- SignPath signature and DigiCert timestamp verified
- Silent install, desktop launch, API health, shutdown, and uninstall passed

Signed installer SHA-256:
`a344717515fd72a570d193907f920d2149c67c515977dc7e5b7ffe2fbbf1d820`
