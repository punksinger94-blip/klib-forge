# K-LIB Forge 1.0.0 Preview 1

This is an early-access GitHub pre-release for installation and workflow
testing. It is not the final trusted 1.0.0 release.

## Important Signing Notice

The Windows installer is Authenticode-signed with the project's self-signed
preview certificate `CN=K-LIB Forge Preview`. Windows will report an unknown or
untrusted publisher. The signature protects artifact integrity but does not
establish public publisher trust.

Install this preview only when downloaded from this GitHub release and after
verifying `SHA256SUMS.txt`. The final stable release will use a publicly trusted
code-signing certificate.

## Included

- React and Tauri desktop application with packaged local API sidecar
- CLI, FastAPI service, Python SDK, and MCP stdio server
- Biomedical evidence-synthesis, production incident-response, and MedChem-KLIB Lite examples
- MedChem RDKit workflow with typed IR preview metadata and research-only safety gate
- MedChem Lab duplicate identity review for records sharing the same InChIKey
- PubChem P1 live enrichment, with ChEMBL P2 and CAS/ZINC/EPA P3 roadmap entries
- MedChem research-agent pipeline for PubChem collection, RDKit/evidence checks,
  K-LIB context packaging, and optional NVIDIA/OpenAI-compatible model synthesis
- Hermes + Minimax-M3 internet-discovery-to-K-LIB MedChem workflow script
- B.AI OpenAI-compatible provider shortcut for `minimax-m3`
- P2/P3 preview registry for built-in and demonstrator K-LIB packages
- Native Anthropic and OpenAI-compatible provider transports
- Arbitrary model IDs and custom OpenAI-compatible endpoints
- Local, Chroma, and Qdrant retrieval adapters
- Prompt-injection scanning, source trust controls, corrections, and eval arena

## Qualification

- Python tests passed locally
- `ruff check packages services tests scripts` passed
- Desktop TypeScript/Vite build passed from `apps/desktop`
- MedChem evidence evals passed 9/9, including typed IR preview and test environments
- MedChem A/B report: without K-LIB 0.12, with K-LIB 1.00, delta +0.88
- Hermes MCP A/B report: without K-LIB 0.00, with K-LIB 1.00, delta +1.00
- Ecosystem smoke passed 6/6 across registry, CLI, API, MCP, MedChem, and release artifacts
- Release readiness report shows 100% pre-release master-plan completion

Signed installer SHA-256:
`45dc389ae31ff90f5345b1037aea58a99a2b8186c3b8dc44a8778adc3f47d76b`
