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

### 2026-06-02 ISSUE-518 — Entrypoint docs drift in demo-facing text

- The canonical API deployment entrypoint is
  `vultron.adapters.driving.fastapi.main:app`, but demo-facing text can drift
  back to legacy module paths if not centrally referenced.
- We found stale `vultron.api.main:app` strings in demo exchange script output
  and notes. This task updated onboarding docs only; script help-text cleanup
  remains a separate follow-up candidate if those strings become user-facing
  blockers.

### 2026-06-02 ISSUE-663 — Case-actor-only broadcast guard

- `BroadcastStatusToPeersNode` needs the current executing actor to match the
  Case Manager before it should fan out participant status updates.
- Tests for the positive broadcast path need a third participant so the case
  manager has at least one non-sender peer to address.
