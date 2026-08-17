---
title: AC-18 satisfied by enriching the existing BT-failure line, not adding a new one
type: learning
timestamp: 2026-08-05
source: ISSUE-1988
signal: design-question
---

ISSUE-1988 AC-18 asked for a new INFO line,
`Actor '<id>' BT execution FAILURE for case '<case_id>': <reason>`, scoped to
"non-owner actors". It was implemented literally first, then deliberately
replaced with an enrichment of the *existing*
`BT execution completed: Status.FAILURE after N ticks - <feedback>` line in
`BTBridge.execute_tree` (falling back to `get_failure_reason()` when the root
carries no feedback message).

Three reasons the literal reading was wrong:

1. **Double-logging.** `execute_tree` already emits one INFO record for every
   terminal status. A second dedicated line meant two INFO records per failure,
   and three for the many callers that also log their own explanation.
2. **No "non-owner" discriminator exists.** `execute_with_setup` has 52 call
   sites and no notion of owner vs non-owner, so the scoping in the AC was not
   implementable as written. Applied unconditionally, it escalated *expected*
   FAILUREs to INFO — e.g. the idempotent `CASE_STATUS_ALREADY_PRESENT` skip in
   `received/status.py`, the non-forward-gap `BufferOutOfOrderEntryNode` return,
   and the ~10 sites that deliberately log `"BT did not fully succeed"` at DEBUG
   precisely because the failure is routine.
3. **No `case_id` to report.** An AST scan found **zero** production
   `execute_with_setup` call sites that pass `case_id=`. Only 5 trigger use
   cases inject it via `_extra_execute_kwargs()`, and those raise before
   reaching the log. Every received-side tree would have rendered
   `for case ''`.

**Guidance for future ACs of this shape:** before adding a "log the reason"
line, check whether an existing record at that point can carry the reason
instead. Also check whether the *absence* of an explanation was the real defect
(it was here) rather than the absence of a line. And when an AC scopes a
behaviour to a subset of actors ("non-owner"), verify a discriminator for that
subset actually exists at the proposed call site before designing around it.

**Promoted**: 2026-08-17 — captured in notes/structured-logging.md (Checklist before adding a 'log the reason' AC).
Docs PR: TBD.
