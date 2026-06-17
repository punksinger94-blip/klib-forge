# Third-Party Notices

K-LIB Forge is Apache-2.0 licensed and includes open-source dependencies under
their respective licenses. Release artifacts include machine-readable Python
and npm CycloneDX SBOMs plus Rust dependency metadata.

The authoritative dependency versions are:

- `requirements/runtime-lock.txt`
- `requirements/dev-lock.txt`
- `apps/desktop/package-lock.json`
- `apps/desktop/src-tauri/Cargo.lock`

Review those files and the release SBOMs for the exact dependency set.

## Optional MedChem dependencies

The `medchem` Python extra uses RDKit under the BSD 3-Clause license. RDKit is
not installed by the default K-LIB Forge dependency set.

- RDKit: https://www.rdkit.org/
- License: https://github.com/rdkit/rdkit/blob/master/license.txt

The exact optional dependency constraint is declared in `pyproject.toml`.
