# MedChem-KLIB Lite

MedChem-KLIB Lite turns molecular structures, scaffolds, compound properties,
bioactivity records, and literature notes into a safe, testable AI research
library. It uses RDKit for chemical structure validation and calculation; the
language model is not treated as a chemistry validator.

This feature does not provide synthesis procedures, human dosage guidance,
clinical decisions, or harmful-compound optimization.

## Alpha capabilities

The current `v0.1-alpha` foundation supports:

- typed MedChem IR metadata with `medchem-ir-preview.1` and the
  `rdkit-medchem-preview` validator profile
- CSV, JSONL, SDF, SMI, and SMILES-text import
- RDKit structure validation
- canonical SMILES, InChI, InChIKey, and molecular formula generation
- molecular weight, exact mass, LogP, HBD, HBA, TPSA, rotatable bonds, rings,
  heavy atoms, formal charge, and fraction Csp3
- Bemis-Murcko scaffold extraction
- Morgan fingerprints and Tanimoto similarity ranking
- name, synonym, id, SMILES, and InChIKey search
- target registry import with gene symbols, organisms, and accessions
- linked bioactivity records with assay context and source identifiers
- linked lab/test-environment records for wet-lab, in-vitro, in-silico, or
  literature-review contexts
- literature record import from CSV, JSONL, Markdown, and text
- citation-grounded compound research briefs
- deterministic evidence checks for record links, citation coverage, grounded
  output, value provenance, compound provenance, and safety refusal
- invalid-molecule and duplicate-InChIKey compile reporting
- stereochemistry diagnostics for undefined centers
- PAINS, BRENK, and NIH structural-alert warnings
- compiled provenance for source refs, RDKit method labels, and value anchors
- a research-boundary safety checker
- RDKit skeletal structure rendering in the MedChem Lab
- deterministic RDKit ETKDGv3 + UFF 3D conformer export as SDF
- source-provider catalog with license notes for PubChem, ChEMBL, CAS Common
  Chemistry, ZINC, and EPA CompTox
- PubChem PUG-REST compound import by name or CID with external IDs, source
  URL, license label, synonyms, SMILES, and provenance

ChEMBL, CAS Common Chemistry, ZINC, and EPA CompTox are tracked as planned
providers. They should be added as opt-in adapters with source-specific license
guards instead of bulk-mirroring every record by default.

For the pre-release plan:

- **P1 active:** PubChem PUG-REST import for names, CIDs, SMILES, synonyms,
  source URLs, and provenance.
- **P2 planned:** ChEMBL target-linked bioactivity subsets with assay and unit
  normalization.
- **P3 planned/restricted:** CAS Common Chemistry, ZINC, EPA CompTox, and COD
  connectors after source-specific license review and subset-size limits.

Duplicate chemical identities are reported as detailed InChIKey groups. The
desktop lab marks them as linked for review so a curator can keep one stable
primary package compound while merging aliases, external IDs, and source
provenance from imported records.

## Installation

RDKit is optional so the normal K-LIB installation stays small:

```powershell
pip install "klib-forge[medchem]"
```

For a source checkout:

```powershell
python -m pip install -e ".[medchem]"
```

## Quick start

```powershell
klib install-example medchem-lite
klib medchem validate -l medchem-lite
```

For a custom package:

```powershell
klib medchem init "My Molecular Evidence" --id my-molecular-evidence
klib medchem import compounds.csv -l my-molecular-evidence
klib medchem compile -l my-molecular-evidence
klib medchem import-targets targets.csv -l my-molecular-evidence
klib medchem import-environments environments.csv -l my-molecular-evidence
klib medchem import-bioactivity activities.jsonl -l my-molecular-evidence
klib medchem import-literature literature.jsonl -l my-molecular-evidence
klib medchem evidence-status -l my-molecular-evidence
klib medchem research "Summarize the evidence for aspirin" -l my-molecular-evidence
klib medchem evidence-evals -l my-molecular-evidence
```

Import structures directly from PubChem when a model cannot access external
chemistry APIs itself:

```powershell
klib medchem sources
klib medchem import-pubchem aspirin caffeine ibuprofen `
  -l my-molecular-evidence
klib medchem import-pubchem 2244 2519 3672 `
  -l my-molecular-evidence --namespace cid
klib medchem compile -l my-molecular-evidence
```

Inspect one structure:

```powershell
klib medchem descriptors "CC(=O)Oc1ccccc1C(=O)O"
klib medchem scaffold "CC(=O)Oc1ccccc1C(=O)O"
klib medchem conformer "CC(=O)Oc1ccccc1C(=O)O" -o aspirin-3d.sdf
```

Search the compiled compound store:

```powershell
klib medchem search aspirin -l medchem-lite
klib medchem similar "CC(=O)Oc1ccccc1C(=O)O" `
  -l medchem-lite --top-k 10
```

Check a request against the safety boundary:

```powershell
klib medchem safety-check `
  "Give me a step-by-step synthesis procedure to manufacture this compound."
```

Run the research-agent pipeline with the local/mock provider:

```powershell
klib medchem agent `
  "Summarize evidence for aspirin and identify next data to import." `
  -l medchem-lite `
  --provider mock `
  --model offline `
  --output build/experiments/medchem-agent-aspirin.json
```

Run the same pipeline with NVIDIA NIM after setting `NVIDIA_API_KEY`:

```powershell
$env:NVIDIA_API_KEY = "..."
klib medchem agent `
  "For Advil, identify the active compound, scaffold, descriptors, duplicate identity notes, and next sources to import." `
  -l medchem-lite `
  --pubchem Advil `
  --provider nvidia `
  --model minimaxai/minimax-m3 `
  --output build/experiments/medchem-agent-advil-nvidia.json
```

The agent report includes collection results, RDKit compile output, evidence
status, evidence evals, the deterministic K-LIB brief, the exact model messages,
the model answer, safety status, duplicate identity groups, and source roadmap.
It does not give the model broad internet access; source import is explicit,
licensed, and repeatable.

Run the wider Hermes internet discovery workflow before K-LIB packaging:

```powershell
$env:NVIDIA_API_KEY = "..."
.\.venv\Scripts\python.exe .\scripts\run-medchem-hermes-internet-klib.py `
  --compound Advil `
  --model minimaxai/minimax-m3 `
  --provider nvidia `
  --output build\experiments\medchem-hermes-internet-klib-advil.json
```

Use B.AI as an OpenAI-compatible endpoint:

```powershell
$env:BAI_API_KEY = "..."
.\.venv\Scripts\python.exe .\scripts\run-medchem-hermes-internet-klib.py `
  --compound Advil `
  --model minimax-m3 `
  --provider b-ai `
  --output build\experiments\medchem-hermes-bai-klib-advil.json
```

Use a Hermes provider that is configured outside K-LIB, such as `mimo`, for
internet discovery and final K-LIB-grounded synthesis:

```powershell
.\.venv\Scripts\python.exe .\scripts\run-medchem-hermes-internet-klib.py `
  --compound Advil `
  --model mimo-v2.5-pro `
  --provider mimo `
  --hermes-provider mimo `
  --klib-provider hermes `
  --klib-model mimo-v2.5-pro `
  --output build\experiments\medchem-hermes-mimo-klib-advil.json
```

That workflow asks Hermes with the configured discovery model to discover
public source candidates, extracts a structured import plan, imports supported
PubChem identities into K-LIB, validates them with RDKit, runs evidence evals,
and then creates the final K-LIB-grounded research-agent report.

## Package layout

```text
medchem-lite/
  manifest.json
  compounds/
    compounds.jsonl
  scaffolds/
    scaffolds.jsonl
  targets/
    targets.jsonl
  environments/
    environments.jsonl
  bioactivity/
    activities.jsonl
  literature/
    notes.md
    records.jsonl
  policies/
    medchem_safety_policy.json
  build/
    medchem_compounds.jsonl
    medchem_compile_report.json
```

All imported and compiled records use the status
`research_reference_only`.

## Data-source strategy

MedChem Lab should make strong but tool-limited models useful by building a
local, licensed, testable chemistry library before the model is asked a
question. The source plan is:

- **PubChem:** active default connector. Use PUG-REST for live compound lookup
  and small curated subsets. Store CIDs, source URLs, license labels, and
  accessed timestamps with every imported compound.
- **ChEMBL:** planned connector for target-linked bioactivity. Import only
  filtered target/assay subsets and normalize activities through the existing
  `activities.jsonl` workflow.
- **CAS Common Chemistry:** planned restricted connector. CAS Common Chemistry
  is CC BY-NC 4.0, so do not include CAS-derived data in commercial release
  bundles unless a separate commercial license is available.
- **ZINC:** planned connector for virtual-screening subsets. Import curated
  subsets, not a full mirror.
- **EPA CompTox/COD:** planned context sources for safety, identifiers, and
  structure cross-checks.

This keeps the release package small and legally reviewable while still letting
MedChem Lab grow beyond hand-entered examples.

## Evidence boundary

The safety checker is a deterministic first gate, not a complete safety
classifier. Applications should also enforce policy at the API/UI boundary and
evaluate model outputs. Allowed uses include structure validation, descriptor
calculation, similarity and scaffold comparison, literature evidence summaries,
and non-actionable research hypotheses.

Blocked uses include synthesis instructions, dosage recommendations, clinical
decision-making, controlled-substance optimization, toxin or poison
optimization, and pathogen or biohazard optimization.

## Linked evidence workflow

Every bioactivity record resolves through three identifiers:

1. `compound_id` links to a validated and compiled molecular structure.
2. `target_id` links to the target registry.
3. Optional `environment_id` links to a lab, assay, in-silico, or literature
   review test environment.
4. `source_ids` link to one or more literature records.

The evidence layer is marked ready only when all three links resolve. The cited
research brief reports linked records without inventing missing activity or
clinical claims.

## Test Environments And Visualization

Use `klib medchem import-environments` to register lab and assay contexts such
as BSL level, temperature, pH, buffer, cell line, organism, platform, and
instrument. Bioactivity rows may reference those records with `environment_id`.
If an activity references an unknown environment, `evidence-status` and
`evidence-evals` flag the missing link.

The desktop MedChem Lab renders 2D skeletal structures through RDKit SVG and
exposes generated 3D SDF conformers for external viewers. The 3D conformer is a
research visualization generated with RDKit ETKDGv3 + UFF; it is not treated as
experimental structure evidence.

## Example result

For the bundled aspirin query, the example dataset returns aspirin at Tanimoto
`1.0`, followed by salicylic acid. The intentionally malformed `C1(CC` record
is retained in the source store but excluded from the compiled store and listed
in `medchem_compile_report.json`. The evidence workflow also returns a
two-source aspirin brief and a nine-check evidence evaluation score covering
referential integrity, citation coverage, value provenance, typed IR metadata,
test environments, activity normalization, compound provenance, grounded
output, and safety refusal.
