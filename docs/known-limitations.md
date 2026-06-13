# Known Limitations

- The `.klib` format remains at `0.1`; future format changes must preserve compatibility.
- Deterministic hash vectors are lightweight and private, but less capable than learned embeddings.
- Chroma is optional and may add substantial installation size.
- Qdrant requires a separately managed Qdrant service.
- Prompt-injection scanning is a defense-in-depth heuristic, not a security proof.
- PDF extraction quality depends on embedded text; scanned PDFs require OCR before ingestion.
- Windows is the supported packaged desktop target for 1.0.
- Code signing requires release-maintainer certificate secrets in the release environment.
- Literature benchmark answer keys are source-backed but are not a substitute for expert review.
