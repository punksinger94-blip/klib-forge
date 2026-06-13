# Release Process

1. Update the version, changelog, lockfiles, and documentation.
2. Run `.\scripts\bootstrap.ps1` and `.\scripts\build.ps1`.
3. Test installation, launch, offline ask/eval/export, shutdown, and uninstall on clean Windows 10 and 11.
4. Create the canonical public repository, add it as the `origin` remote, enable
   private vulnerability reporting, and add verified project URLs to
   `pyproject.toml` only after those URLs exist.
5. Configure the GitHub `release` environment with the Windows signing
   certificate secrets. Configure separate `testpypi` and `pypi` environments
   with trusted publishing for their respective package indexes.
6. Run `.\scripts\release.ps1` locally. Unsigned candidates require the explicit
   `-AllowUnsigned` switch and are not public-release artifacts.
7. Commit, create the annotated `v1.0.0` tag, and push it.
8. The release workflow signs the installer, publishes Python artifacts, writes
   SBOM/checksum files, and creates the GitHub release.

Never upload files from an uncleared `dist/` directory.
