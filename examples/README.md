# Built-in examples

K-LIB Forge installs its examples from the versioned catalog in
`klib_core.examples` so the CLI, API, desktop, and tests use the same source of
truth.

Available packages:

- `biomedical-evidence-synthesis`: five curated primary-study sources and five
  citation-aware quantitative biology evals.
- `production-incident-response`: an incident record, runbook, reliability
  policy, and three evidence-preserving response evals.

List and install them with:

```powershell
klib example-catalog
klib install-example biomedical-evidence-synthesis
klib install-example production-incident-response
```
