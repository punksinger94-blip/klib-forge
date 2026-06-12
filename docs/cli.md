# CLI

```text
klib init NAME
klib list
klib info
klib add PATH
klib compile
klib search QUERY
klib ask PROMPT
klib glossary add SOURCE TARGET
klib rule add BODY
klib example add --input TEXT --output TEXT
klib correct --input TEXT --bad-output TEXT --corrected-output TEXT
klib eval
klib diff
klib export DESTINATION
klib import ARCHIVE
klib models
klib model-test
klib nvidia-ab
```

Commands discover a package from the current directory and its parents. Use
`--library ID` when working outside a package folder.

`klib nvidia-ab` reads `NVIDIA_BASELINE_API_KEY` and
`NVIDIA_KLIB_API_KEY` from the current process. Prefer the repository wrapper,
which prompts for both values without placing them in shell history:

```powershell
.\scripts\run-nvidia-biological-ab.ps1 -Repeats 3 -Crossover
```
