## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-06-02 LOGGING-667 — Logging level tuning completion

The code-review agent identified two tree creation functions in receive_report_case_tree.py and validate_tree.py that were initially missed during the bulk update. The code-review agent correctly flagged this as a [BLOCKING] issue and provided clear evidence that all tree creation functions should be consistently at INFO level. After fixing those two functions, all tests and linters passed cleanly.

**Learning**: When bulk-updating logging levels across multiple files, use `grep` to verify consistency of the pattern before committing. The code-review agent's systematic approach caught what could have been an inconsistency in the merge.

### 2026-06-02 ISSUE-666 — Notes frontmatter and docs-build warning constraints

- `notes/*.md` frontmatter currently enforces `superseded_by` as a single
  non-empty string (not a YAML list), so split-note migrations should point
  `superseded_by` at one canonical successor and list sibling files in
  `related_notes` or body text.
- `.github/scripts/mkdocs-build-strict.sh` suppresses several known griffe
  false positives but still treats unknown-key warnings like `context` and
  `pytest` as real build failures.
