---
title: mkdocs-build-strict.sh exits with arithmetic error when there are zero warnings
type: learning
timestamp: "2026-08-28T00:00:00Z"
source: ISSUE-2785
signal: tooling-issue
---

`.github/scripts/mkdocs-build-strict.sh` fails with a bash arithmetic syntax error when
the mkdocs build produces **zero** warnings.

Root cause: lines 22, 25, and 28 all use the pattern:

```bash
VAR=$(grep -c "pattern" "$FILE" || echo 0)
```

When `grep -c` finds 0 matches it exits with status 1 and prints `0`. The `|| echo 0`
fallback then also runs, so the command substitution captures two `0` tokens (`"0\n0"`).
The subsequent arithmetic `$((TOTAL - FALSE))` fails:

```text
.github/scripts/mkdocs-build-strict.sh: line 34: 0
0: syntax error in expression (error token is "0")
```

Workaround: run `uv run mkdocs build --strict` directly to confirm zero real warnings.
The script works correctly when at least one warning exists (the count is then non-zero
and `|| echo 0` never fires).

Fix: replace `grep -c … || echo 0` with the safe form
`$(grep -c "pattern" "$FILE" 2>/dev/null; true)` to force exit 0, or pipe through
`head -1` to take only the first token and discard any fallback echo output.

Discovered during PR #2853 (issues #2785–#2788) when the build had zero real warnings.

## Audit disposition (2026-09-02)

This entry correctly identified the root cause (lines 22, 25, 28). Fixed in this audit. Under BW-07-006 the second witness should have triggered a filed issue rather than a third learning file.
