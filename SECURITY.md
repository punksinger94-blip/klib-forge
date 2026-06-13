# Security Policy

## Reporting

Do not open a public issue for vulnerabilities involving archive extraction,
source isolation, secret exposure, model routing, or prompt injection. Use
GitHub private vulnerability reporting on the canonical repository. Repository
owners must enable private vulnerability reporting before a public release.

## Security boundaries

- `.klib` imports reject archives with multiple roots or path traversal.
- Online model access is disabled by default per package.
- Retrieved documents are labeled as evidence and never promoted to system
  instructions.
- The API binds to `127.0.0.1` by default and has a narrow desktop CORS policy.
- The desktop runtime selects an ephemeral localhost port and terminates its
  packaged API sidecar when the app exits.
- K-LIB Forge does not store provider API keys in package files.
- NVIDIA A/B credentials are read from process environment variables and are
  excluded from run reports. The benchmark wrappers prompt with masked input
  and clear keys that they introduced when the command finishes.

Never commit, paste, or include provider keys in issue text, chat messages,
screenshots, shell arguments, or benchmark reports. Revoke and replace any key
that has been disclosed.

The Trust Gate is defense in depth, not a sandbox or malware scanner. Do not
expose the local API to untrusted networks.
