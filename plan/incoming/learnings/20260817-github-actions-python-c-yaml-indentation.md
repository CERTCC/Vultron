---
title: Multi-line python3 -c in GitHub Actions YAML run block causes actionlint YAML parse failure
type: learning
timestamp: 2026-08-17
source: ISSUE-2312
signal: tooling-issue
---

When embedding multi-line Python in a GitHub Actions `run: |` block via
`python3 -c "..."`, the Python code lines must stay within the YAML block
scalar's indentation level.  If the code starts at column 0 (or any
indentation less than the block's base), YAML terminates the block early and
`actionlint` fails with:

```text
could not parse as YAML: yaml: line N: could not find expected ':'
```

**Root cause**: YAML literal block scalars auto-detect indentation from the
first content line.  Any subsequent line at a lower indentation level ends the
block; the remainder is parsed as bare YAML and fails.

**Fix**: Collapse the Python to a single semicolon-separated line that fits on
one line of the `run:` block:

```yaml
        run: |
          python3 -c "import json,os,pathlib; ..."
```

For longer scripts, write them to a file in a prior step and execute them, or
use `jq -n` for pure JSON generation.
