---
title: "Two nodes/ modules sat at 499 and 495 lines against BTND-07-004's 500-line cap, so any change to them forces a decomposition"
type: learning
timestamp: "2026-08-12T00:00:00Z"
source: ISSUE-2235
signal: concern
---

BTND-07-004 caps modules under `nodes/` at 500 lines, enforced by
`test/core/behaviors/test_btnd07_structure.py::test_leaf_module_line_count`. At
the start of this fix:

- `vultron/core/behaviors/status/nodes/append.py` — 499 lines
- `vultron/core/behaviors/sync/nodes/effects.py` — 495 lines

Both are exactly the modules ISSUE-2235 had to touch. Adding a docstring
paragraph and a ~25-line method was enough to blow the cap in both, so the bug
fix had to carry an unrelated file-splitting change (`rm_validation.py`,
`participant_status_effect.py`) to get a green suite. That inflates the diff a
reviewer has to read for a behavioural fix, and it happened at the least
convenient moment — after the fix was verified, in the final lint/test loop.

The cap itself is doing its job; the problem is that there is no warning band. A
module at 495 lines is a decomposition that was deferred, and the next person to
touch it pays for it. Worth considering: a second, softer assertion (or a CI
annotation) at ~90% of the limit so modules get split by whoever is already in
context, not by whoever arrives next with an unrelated change.

Note also that decomposition is not free of churn beyond the module: both splits
required updating package `__init__.py` re-exports, module docstrings enumerating
the moved classes, and test files that imported the class directly rather than
through the package. `test/core/behaviors/sync/nodes/test_effects.py` turned out
to test only the one class being moved and was renamed to match.

**Promoted**: 2026-08-17 — captured in GitHub #2329 (Idea: soft-warning CI annotation at 90% of 500-line cap).
Docs PR: TBD.
