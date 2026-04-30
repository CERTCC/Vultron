---
title: BUG-386 — Defer unresolved Accept.object_ references (resolved via sender-side fix)
type: implementation
date: 2026-04-30
source: TASK-BUG-386
---

## TASK-BUG-386 — Defer unresolved `Accept.object_` references

**Resolution**: Closed by prior work in commit `62cdc48e` ("Fix invite response
parsing and reply links"). The parser now correctly embeds inline typed objects
in `Accept` and `Reject` activities, so the receiver always has the referenced
`Invite`/`Offer` object available after rehydration. Dead-letter records are no
longer created for well-formed `Accept` activities.

The receiver-side deferred-queue approach described in the task was not needed:
the sender-side fix eliminates the out-of-order scenario for spec-compliant
senders. Regression tests added in `aa50d7cd` (test(dr-05)) verify the
inline-object invariant.

**Outcome**: No code changes required. Task removed from implementation plan.
