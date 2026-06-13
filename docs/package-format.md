# `.klib` Package Format v0.1

A `.klib` file is a ZIP archive containing one top-level package folder.

```text
my-library/
  manifest.json
  sources/
  chunks/chunks.jsonl
  glossary.json
  rules.md
  examples.jsonl
  corrections.jsonl
  evals/
  prompts/
  policies/
  indexes/
  runs/
  build/
```

`manifest.json` is validated by
`specs/klib-package-spec/manifest.schema.json`. The package id is a lowercase,
hyphenated stable identifier. Package content licenses are declared separately
from the K-LIB Forge software license.

Generated indexes are portable optimization data. The source, glossary, rule,
example, correction, and eval files remain the canonical knowledge inputs.

Retrieval policies can select `local`, `chroma`, or `qdrant` vector adapters and
can enable hybrid lexical/vector fusion. External vector stores are rebuildable
optimizations and are never canonical package content.
