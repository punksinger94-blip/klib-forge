# CLI

```text
klib init NAME
klib list
klib info
klib add PATH
klib compile
klib search QUERY
klib suggest
klib trust
klib runs
klib ask PROMPT
klib glossary add SOURCE TARGET
klib rule add BODY
klib example add --input TEXT --output TEXT
klib correct --input TEXT --bad-output TEXT --corrected-output TEXT
klib eval
klib arena --candidate mock:offline-demo --candidate ollama:gemma3
klib diff
klib export DESTINATION
klib import ARCHIVE
klib models
klib model-test
klib nvidia-ab
klib nvidia-literature-ab
klib profile add NAME --provider PROVIDER --model MODEL
klib profile list
klib profile delete ID
klib-mcp
```

Commands discover a package from the current directory and its parents. Use
`--library ID` when working outside a package folder.

`klib nvidia-ab` reads `NVIDIA_BASELINE_API_KEY` and
`NVIDIA_KLIB_API_KEY` from the current process. Prefer the repository wrapper,
which prompts for both values without placing them in shell history:

```powershell
.\scripts\run-nvidia-biological-ab.ps1 -Repeats 3 -Crossover
```

For the primary-literature benchmark, use:

```powershell
.\scripts\run-nvidia-literature-biological-ab.ps1 `
  -Model "minimaxai/minimax-m3" `
  -Repeats 3 `
  -Crossover
```
