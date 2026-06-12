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
