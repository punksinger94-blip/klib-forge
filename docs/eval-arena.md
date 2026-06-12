# Eval Arena v0.1

Evaluation files are JSON documents in `evals/`. The v0.1 runner supports:

- `must_include`
- `must_not_include`
- `json_valid`
- `citation_required`

Each check contributes equally to the score. A correction can automatically
create a regression eval, making user feedback executable on future model runs.

