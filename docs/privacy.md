# Privacy and Data

K-LIB Forge has no telemetry and no cloud account requirement.

- Package sources, indexes, corrections, profiles, and model run history are local.
- Model profiles store the name of an API-key environment variable, never its value.
- Online providers are blocked unless a package explicitly enables online models.
- Online requests send the assembled prompt and retrieved evidence to the selected provider.
- The optional Anthropic knowledge collector sends only its command-line topic and
  approved web-domain allowlist. It has no repository, filesystem, shell, or code tools.
- MedChem structure validation, descriptors, scaffolds, and similarity run locally
  through the optional RDKit dependency. The alpha has no PubChem or ChEMBL connector.
- The packaged API binds to loopback and is not intended for untrusted networks.
- Exported `.klib` archives can contain source material and run files. Review them before sharing.

Delete a managed library from the desktop or CLI to remove its package files.
Provider retention and training policies are controlled by the selected provider.
