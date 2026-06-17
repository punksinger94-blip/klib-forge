# Private Anthropic Knowledge Collection

Use `scripts/collect-anthropic-knowledge.py` to research public information with
Claude Opus without granting access to the repository, local files, a shell, or
credentials.

The collector sends only:

- the topic typed on the command line;
- the approved web-domain allowlist;
- fixed research and citation instructions.

It uses Anthropic's hosted web-search tool. It does not use the Files API, Bash,
computer use, local MCP servers, or code-execution tools.

## Preview the request

```powershell
.\.venv\Scripts\python.exe .\scripts\collect-anthropic-knowledge.py `
  "Recent primary studies on bacterial RNA thermometers" `
  --domain pubmed.ncbi.nlm.nih.gov `
  --domain pmc.ncbi.nlm.nih.gov `
  --domain academic.oup.com `
  --dry-run
```

The request is written under ignored `build/knowledge-staging/`. Inspect it
before spending API credit.

## Run the collection

Run the collector. It requests the API key with masked input when
`ANTHROPIC_API_KEY` is not already set:

```powershell
.\.venv\Scripts\python.exe .\scripts\collect-anthropic-knowledge.py `
  "Recent primary studies on bacterial RNA thermometers" `
  --domain pubmed.ncbi.nlm.nih.gov `
  --domain pmc.ncbi.nlm.nih.gov `
  --domain academic.oup.com `
  --max-searches 5
```

Review `knowledge.md`, `sources.json`, and the raw `response.json`. Import only
approved material into a K-LIB package. The API key is kept in process memory
and is not written to these files.

## Privacy boundary

Anthropic states that commercial API inputs and outputs are not used to train
models by default. Standard retention and feature-specific storage still apply.
The Files API is intentionally excluded because uploaded files are stored and
that feature is not eligible for zero data retention.

Never pass secrets, private code, unpublished documents, signing keys, `.env`
files, or credentials as a research topic.
