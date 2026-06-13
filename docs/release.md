# Release Process

1. Update the version, changelog, lockfiles, and documentation.
2. Run `.\scripts\bootstrap.ps1` and `.\scripts\build.ps1`.
3. Complete the deep qualification matrix and update
   `docs/release-qualification-1.0.0.md` with the exact evidence.
4. Test installation, launch, offline ask/eval/export, shutdown, and uninstall on clean Windows 10 and 11.
5. Create the canonical public repository, add it as the `origin` remote, enable
   private vulnerability reporting, and add verified project URLs to
   `pyproject.toml` only after those URLs exist.
6. Configure the GitHub `release` environment with the Windows signing
   certificate secrets. Configure separate `testpypi` and `pypi` environments
   with trusted publishing for their respective package indexes.
7. Run `.\scripts\release.ps1` locally. Unsigned candidates require the explicit
   `-AllowUnsigned` switch and are not public-release artifacts.
   `.\scripts\release-doctor.ps1 -Public` must pass before tagging.
8. Commit, create the annotated `v1.0.0` tag, and push it.
9. The release workflow signs the installer, publishes Python artifacts, writes
   SBOM/checksum files, and creates the GitHub release.

Never upload files from an uncleared `dist/` directory.

## Direct public release

When GitHub CLI is installed and authenticated as `punksinger94-blip`, and the
trusted PFX variables are configured, the final signing and GitHub publication
can be completed with one command:

```powershell
$env:WINDOWS_CERTIFICATE_PATH = "C:\secure\trusted-code-signing.pfx"
$env:WINDOWS_CERTIFICATE_PASSWORD = "<PFX password>"
gh auth login
.\scripts\complete-public-release.ps1
```

The command verifies the GitHub account, creates or reuses
`punksinger94-blip/klib-forge`, refuses an invalid installer signature, runs the
public release doctor, pushes `main` and the annotated `v1.0.0` tag, and uploads
the installer, wheel, source archive, checksums, and all release metadata.
