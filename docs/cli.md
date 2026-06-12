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
```

Commands discover a package from the current directory and its parents. Use
`--library ID` when working outside a package folder.

