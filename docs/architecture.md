# Architecture

```text
React/Tauri IDE or CLI
          |
       FastAPI
          |
      K-LIB Core
  + package manager
  + source compiler
  + local retrieval
  + prompt builder
  + model providers
  + eval runner
  + knowledge diff
          |
  SQLite + package files
```

The core package has no dependency on the UI or API. The CLI calls it directly,
and the API is a thin transport layer. This keeps `.klib` behavior consistent
for desktop users and automation.

## Compilation

1. Resolve registered source files.
2. Extract and clean text.
3. Split text into overlapping chunks.
4. Persist portable chunk JSONL.
5. Build a deterministic local TF-IDF index.
6. Extract top keywords.
7. Write build metadata and a Knowledge Diff snapshot.

## Prompt order

1. Runtime safety policy
2. Package identity and mode
3. Glossary
4. Rules
5. Examples
6. Retrieved context
7. User request

Source documents remain evidence and cannot override runtime instructions.

