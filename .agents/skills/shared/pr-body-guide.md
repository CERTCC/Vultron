# PR Body Guide

All PRs opened by agents MUST use the structured templates below.
Reference this file from the "Open PR" step of any skill that calls
`gh pr create`.

---

## Template: Implementation PRs

Use for `build`, `bugfix`, and any PR that modifies `.py` files.

```markdown
- Closes #N
- Closes #M   <!-- one line per issue; GitHub expands the title automatically -->

## Summary

<1–2 sentences: what this PR does and why. Present tense: "Adds…", "Fixes…",
"Replaces…". Focus on the outcome.>

## Motivation

<Why this change is needed. **Omit this section** if the Summary already
captures the full rationale.>

## Changes

- **`path/to/file.py`**: <what changed and why>
- **`path/to/other.py`**: <what changed and why>
- **`test/path/test_file.py`**: <what tests were added or changed>

## Verification

- All N unit tests pass (M new)
- Black, flake8, mypy, pyright clean
- [x] AC-1: ...   <!-- include when the closed issue listed acceptance criteria -->
```

### Implementation PR rules

- Closing references (`Closes #N` / `Fixes #N`) go at the **top**, one per
  bullet line, so GitHub expands the issue title in the PR sidebar.
- **Summary**: required; 1–2 sentences, present tense.
- **Motivation**: optional; omit when Summary is self-explanatory.
- **Changes**: required; use backtick-wrapped file paths and concrete
  descriptions. Do not just echo the commit message.
- **Verification**: required for any PR that modifies `.py` files. Include
  the actual total test count and the number of new tests added. Tick off
  acceptance criteria from the issue when they are listed.

---

## Template: Docs-Only PRs

Use for `plan-issue`, `learn`, and any PR that touches only `.md`, `.yaml`,
or other non-Python files.

```markdown
- Closes #N

## Summary

<1–2 sentences: what docs, specs, or notes were added or updated and why.>

## Changes

- **`path/to/file.md`**: <what changed>
- **`specs/file.yaml`**: <what changed>
```

### Docs-only PR rules

- No Verification section — no Python was changed, no test suite ran.
- Keep Changes concise; list meaningful files only (not `README.md` unless
  it was substantively updated).
