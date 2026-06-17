# MedChem-KLIB Lite

MedChem-KLIB Lite turns molecular structures, scaffolds, compound properties,
bioactivity records, and literature notes into a safe, testable AI research
library.

The dataset contains familiar reference molecules and one intentionally invalid
SMILES record. It demonstrates structure validation, descriptor calculation,
Bemis-Murcko scaffold extraction, 2D skeletal structure rendering, generated
3D SDF conformers, fingerprint similarity, linked targets, lab/test
environments, bioactivity, cited literature briefs, regression evaluation, and
safety refusal.

It does not contain synthesis procedures, dosing guidance, clinical claims, or
harmful-compound optimization.

The bundled package uses PubChem as the active P1 enrichment path for public
compound identities. ChEMBL is planned for P2 target-linked bioactivity
subsets; CAS Common Chemistry and ZINC are P3 opt-in connectors after license
and subset review. Duplicate chemical identities are surfaced as InChIKey
review groups instead of silently merging records.

```powershell
klib install-example medchem-lite
klib medchem validate -l medchem-lite
klib medchem similar "CC(=O)Oc1ccccc1C(=O)O" -l medchem-lite
klib medchem conformer "CC(=O)Oc1ccccc1C(=O)O" -o aspirin-3d.sdf
```
