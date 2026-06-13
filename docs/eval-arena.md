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
