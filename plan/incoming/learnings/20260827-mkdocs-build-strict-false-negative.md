---
title: mkdocs-build-strict.sh warning counter has bash syntax error that prints misleading failure message
type: learning
timestamp: 2026-08-27
source: ISSUE-2523
signal: tooling-issue
---

`.github/scripts/mkdocs-build-strict.sh` has a syntax error in its
warning-count arithmetic that fires when the filtered warning count is zero:

```text
.github/scripts/mkdocs-build-strict.sh: line 31: 0
0: syntax error in expression (error token is "0")
✗ Documentation build failed with  real warning(s)
```

Despite this output, the script exits with code **0** and the docs build
completed successfully (`Documentation built in N seconds`). The mismatch
is confusing: the "failed" message appears even when there are no real
warnings.

**How to apply:** When running `mkdocs-build-strict.sh`, check the exit code
(`echo $?`) rather than the prose message to determine pass/fail. A `0` exit
with a "failed" message is a script bug, not a documentation error. The docs
build itself is authoritative — look for `Documentation built in N seconds` in
the output to confirm the build completed.

A fix to the script's arithmetic guard would prevent the false negative.
