# Security Policy

## Reporting

Do not open a public issue for vulnerabilities involving archive extraction,
source isolation, secret exposure, model routing, or prompt injection. Report
them privately to the repository maintainers.

## v0.1 security boundaries

- `.klib` imports reject archives with multiple roots or path traversal.
- Online model access is disabled by default per package.
- Retrieved documents are labeled as evidence and never promoted to system
  instructions.
- The API binds to `127.0.0.1` by default and has a narrow desktop CORS policy.
- K-LIB Forge does not store provider API keys in package files.

The v0.1 Trust Gate is foundational rather than complete. Do not expose the
local API to untrusted networks.

