---
title: mkdocs-build-strict.sh bash arithmetic bug causes false exit-code failures
type: learning
timestamp: 2026-08-27
source: ISSUE-2520
signal: tooling-issue
---

`.github/scripts/mkdocs-build-strict.sh` fails with a bash arithmetic syntax
error when the real WARNING count is zero. The script prints:

```text
✗ Documentation build failed with  real warning(s)
```

but exits with code 0. The count variable is empty (no WARNINGs), so the
arithmetic expression `$((count))` fails with "syntax error in expression
(error token is '0')".

**Workaround**: count real WARNING lines manually:

```bash
.github/scripts/mkdocs-build-strict.sh 2>&1 | grep -c "WARNING" || true
```

Zero output means the build is clean regardless of the script's exit code.

**Why it matters**: CI passes (exit 0 is correct), but local developer
experience is broken — the failure message suggests docs are broken when
they are not.

**Suggested fix**: guard the count variable:
`count=${count:-0}` before the arithmetic comparison.
