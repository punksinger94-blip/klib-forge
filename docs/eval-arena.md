# Eval Arena v0.1

Evaluation files are JSON documents in `evals/`. The v0.1 runner supports:

- `must_include`
- `must_not_include`
- `json_valid`
- `citation_required`

Each check contributes equally to the score. A correction can automatically
create a regression eval, making user feedback executable on future model runs.

## NVIDIA biological A/B benchmark

`klib nvidia-ab` installs a synthetic biology package about the fictional
organism Vesperomyces marina. Fictional facts prevent pretrained model knowledge
from hiding the effect of retrieval and K-LIB policy.

The baseline and K-LIB conditions use the same model, questions, temperature,
and token limit. Only the K-LIB condition receives retrieved evidence and
package rules. Exact identifiers, numeric values, and citations determine the
score.

Use `--crossover` to repeat the experiment with API key assignments swapped.
This is the preferred real test because it distinguishes a K-LIB effect from a
credential-specific routing, quota, or timing effect.

## Primary-literature biology benchmark

`klib nvidia-literature-ab` installs a separate package with five questions
whose expected answer details are held in eval metadata. The questions cover
recent primary studies and require paper-specific mechanisms, identifiers,
quantities, and numeric citations.

The baseline receives the question without K-LIB context. The K-LIB condition
receives a retrieved, concise evidence record containing the study title, DOI,
source URL, and curated facts. The benchmark therefore measures grounded
recovery of supplied literature evidence rather than general biological
expertise.

The included answer key has deterministic automated checks but has not been
independently reviewed by a biology subject-matter expert.

## Hermes Agent + NVIDIA public-world benchmark

`scripts/run-hermes-nvidia-public-ab.py` runs the public primary-literature
benchmark through two different paths:

- **NVIDIA only:** direct NVIDIA API call with no tools, K-LIB, web search, or
  local files.
- **Hermes + K-LIB:** Hermes Agent uses the same NVIDIA model while calling the
  `klib_forge` MCP tools to search `biomedical-evidence-synthesis`.

The runner invokes Hermes with `hermes chat -Q`, because that noninteractive
entrypoint exposes MCP tools to the agent. The shorter `hermes -z` one-shot path
is useful for plain model prompts, but it did not expose `klib_forge` during the
release qualification run.

This is the preferred non-fiction demo because the questions are backed by
public primary-study records with DOI/PMCID/source URLs. It measures whether
Hermes plus K-LIB recovers exact paper-specific identifiers, mechanisms,
quantities, and numeric citations better than the model alone.

```powershell
$env:NVIDIA_API_KEY = "nvapi-..."
.\.venv\Scripts\python.exe .\scripts\run-hermes-nvidia-public-ab.py `
  --model minimaxai/minimax-m3 `
  --hermes-timeout 180 `
  --hermes-max-turns 12
```

During release qualification, `minimaxai/minimax-m3` handled raw NVIDIA tool
calling but stalled inside the Hermes MCP search loop. For the public release
video, use a NVIDIA model that completed the Hermes + K-LIB tool path:

```powershell
.\.venv\Scripts\python.exe .\scripts\run-hermes-nvidia-public-ab.py `
  --model nvidia/llama-3.3-nemotron-super-49b-v1.5 `
  --hermes-timeout 180 `
  --hermes-max-turns 12
```

If Hermes does not recognize `--provider nvidia` on the local machine, keep the
same NVIDIA API key and run:

```powershell
$env:OPENAI_BASE_URL = "https://integrate.api.nvidia.com/v1"
.\.venv\Scripts\python.exe .\scripts\run-hermes-nvidia-public-ab.py `
  --model minimaxai/minimax-m3 `
  --hermes-provider openai-compatible
```
