# Dependency Security Intelligence

Dependency Security Intelligence is a live-evidence K-LIB package for reviewing
pinned Python dependencies. It queries the public [OSV API](https://osv.dev/),
normalizes exact package/version matches into a local source document, compiles
that document into K-LIB, and can then ask a local or hosted model to produce a
cited report.

It is deliberately not an unrestricted browsing agent. The collector only
sends package names and pinned versions to OSV; it does not send source code,
repository contents, credentials, or environment variables. The resulting OSV
response is treated as evidence, never as instructions.

## What it proves

The package makes live findings reproducible:

- each result records the package and exact installed version
- each matched advisory keeps its OSV identifier, aliases, reference URLs, and
  reported fixed versions
- every model answer is governed by rules requiring citations and explicit
  uncertainty
- a no-match result is documented as "no matching OSV record returned", not a
  claim that the dependency is secure
- the built-in evals protect the evidence contract and the pypdf advisory
  regression fixture

## Start an audit

Install the package once:

```powershell
klib install-example dependency-security-intelligence
```

Collect live evidence for a pinned requirements file:

```powershell
klib security audit requirements\runtime-lock.txt
```

To give a local Ollama model the current evidence, add a question. Replace the
model name with the model installed on the machine; this example uses the
user's Gemma profile.

```powershell
klib security audit requirements\runtime-lock.txt `
  --provider ollama `
  --model gemma4:e4b `
  --question "List only confirmed advisory matches. For each, give the package, installed version, advisory ID, reported fixed version, evidence URL, and uncertainty. Cite every finding."
```

The live audit is stored as a trusted local source named
`live-osv-dependency-audit.md` inside the K-LIB package. A refresh replaces the
previous live audit instead of silently accumulating stale reports.

## Source hierarchy

OSV is the live match source. Follow advisory references to the maintainer or
GitHub Advisory Database for confirmation. The CISA Known Exploited
Vulnerabilities catalog should be used only to make an explicit exploitation
prioritization statement. Its absence is not evidence that exploitation is
impossible.

## Boundaries

This package helps prioritize dependency review. It does not establish runtime
reachability, exploitability in a particular deployment, compatibility of an
upgrade, or a complete security posture. Review advisory evidence and test
upgrades before release.
