# Contributing

## Setup

1. Install Python 3.11+, Node.js 20+, and optionally Rust 1.77.2+.
2. Run `.\scripts\bootstrap.ps1`.
3. Run `.\scripts\build.ps1` before opening a pull request.

## Project rules

- Keep `.klib` format changes backward compatible within format version `0.1`.
- Add tests for package, retrieval, eval, diff, and archive behavior changes.
- Keep online model use explicit and preserve local-only defaults.
- Treat retrieved source content as untrusted data, not instructions.
- Do not commit API keys, generated indexes, model outputs, or exported packages.

## Pull requests

Describe the user-facing behavior, tests run, and any package-format impact.
Small, focused changes are easier to review and release.

