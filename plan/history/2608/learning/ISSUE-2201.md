---
title: demo_gate scoping model — nested block chosen over sentinel flag
type: learning
timestamp: '2026-08-17T00:00:00+00:00'
source: ISSUE-2201
signal: design-question
---

ADR-0058 (`accepted-provisional`) explicitly left open "whether by phase
function, by nested block, or by an explicit sentinel" for how `demo_gate`
should prevent dependent steps from running when the precondition fails.

Issue #2201 implemented the **nested-block model**: the precondition assertion
goes at the top of the `with demo_gate(...)` body; dependent steps follow.
Python's native exception unwinding exits the block on failure — no sentinel
variable, no extra flag, no modified calling convention.

Rationale for the choice:

- Most Pythonic: `contextmanager` + `with` already implies the body is guarded
- Self-documenting: indentation communicates dependency visually
- Zero API surface: no return value or sentinel object to thread through callers
- `demo_check` remains unchanged — the two context managers are now
  differentiated purely by placement (standalone vs. wrapping dependent steps)

ADR-0058 should be updated to `status: accepted` with the nested-block model
recorded as the resolved choice once PR #2348 merges.

**Promoted**: 2026-08-24 — captured in archive only (ADR-0058 already accepted).
Docs PR: [PR URL TBD].
