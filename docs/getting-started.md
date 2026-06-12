# Getting Started

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Create and compile

```powershell
klib init "Project Helper" --domain coding
Set-Location .\project-helper
klib add C:\path\to\documentation
klib glossary add latency "response time"
klib rule add "Keep file paths and code identifiers unchanged."
klib compile
klib search "where is configuration loaded"
```

## Ask

Ollama:

```powershell
klib ask "Explain the configuration flow" --provider ollama --model gemma3
```

Offline smoke test:

```powershell
klib ask "Explain the configuration flow" --provider mock --model offline-demo
```

## Correct and test

```powershell
klib correct `
  --input "Explain latency" `
  --bad-output "Delay" `
  --corrected-output "Response time" `
  --lesson "Use the package glossary."

klib eval --provider mock --model offline-demo
klib diff
```

