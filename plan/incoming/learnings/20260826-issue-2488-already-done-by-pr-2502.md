---
title: "Issue #2488 already satisfied by PR #2502 — missing Closes footer"
type: learning
timestamp: "2026-08-26"
source: ISSUE-2488
signal: process-issue
---

Issue #2488 ("Resolve annotation-time import cycles in vultron/core/models/")
was fully implemented by PR #2502 ("refactor: detangle core/models/ import
cycles by moving has_case_statuses()"), which closed #1933 but not #2488.

All 4 ACs were satisfied:

- `python -W error` import of `_helpers` exits 0
- 0 annotation-only cycles in `vultron/core/models/` (static analysis)
- All tests pass
- All callers updated to new import location

The root cause was that PR #2502's footer only said `Closes #1933`. Issue
Issue #2488 was created from docs PR #2485 as an implementation task after #1933
was already in flight, and the two issues were never linked.

**Takeaway**: Before implementing, verify every AC against `origin/main`.
If all ACs pass, close with a reference comment — no PR needed.
(AGENTS.md pitfall: "Verify Issue ACs Against Current Code Before Starting")
