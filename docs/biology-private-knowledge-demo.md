# Biology Private-Knowledge Demo

The first nine `biology-core-reference` documents contain public textbook
facts. A capable base model may already answer many of those questions without
retrieval.

The tenth document, `10-aster-9-internal-assay.md`, is different. It is a
clearly labeled fictional internal protocol containing exact organization-only
values. It demonstrates the practical K-LIB use case without presenting
fictional details as real science.

## Strong demo prompt

```text
In the fictional internal Aster-9 assay, provide: the Lumen-R7 priming dose
and time; the hypoxia oxygen percentage and duration; the Vela-B pH; the valid
positive ratio and readout minute; and both abort thresholds. If K-LIB search
is available, use it. Do not guess. Cite the source when available.
```

Expected baseline behavior: admit that the internal values are unavailable
instead of inventing them.

Expected K-LIB behavior:

- 7.5 microliters per 2.0 milliliters, primed for 14 minutes
- 1.7% oxygen for 42 minutes
- Vela-B pH 7.28
- positive ratio at least 1.35 at minute 11
- abort above 34.2 degrees Celsius
- abort if the ratio exceeds 2.10 before minute 4
- cite `10-aster-9-internal-assay.md`

## Automated local comparison

```powershell
python scripts/run-biology-private-ab.py --model gemma4:e4b
```

The script runs the same local model at temperature zero across four
private-protocol evaluations. The baseline receives no K-LIB context. The
grounded condition receives retrieved context, rules, examples, and glossary
terms from `biology-core-reference`.

## Measured result

Local run on June 15, 2026 using `gemma4:e4b`:

| Condition | Average score |
| --- | ---: |
| Without K-LIB | 0.00 |
| With K-LIB | 100.00 |
| Improvement | +100.00 |

All four private-protocol evaluations changed from `0.00` to `100.00`. The
baseline correctly declined to invent unavailable values; the grounded
condition recovered the exact values and cited retrieved evidence.
