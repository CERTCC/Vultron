---
title: "state_entered preconditions use post-transition CS patterns"
type: learning
timestamp: "2026-07-15T00:00:00Z"
source: ISSUE-1425
---

## Observation

In `state_entered` BehavioralSpec groups, the `cs_pattern` precondition is
evaluated **after** the state transition fires, not before.

**The bug**: CSB-13-001 (Enter CS.X) initially used `cs_pattern: "...px."` —
but the X bit is already set when `state_entered: CS.X` fires, so `x` lowercase
can never match. The precondition was dead code.

**The fix**: Use the post-transition pattern `"...pX."` (X uppercase, P
lowercase) to match the specific case where X was just set but P was not yet
set — triggering the pX→PX invariant handler.

## Pattern

For `state_entered` groups:

- The triggered dimension's bit is **uppercase** in the precondition pattern.
- Other dimensions reflect their state **at the moment the trigger fires**.
- Example (CSB-13-001): `"...pX."` means "X is now set, P was not yet set" —
  exactly the precondition for the pX→PX invariant (C-15).

Compare to `message_received` groups where `cs_pattern` reflects the
pre-message state (the message hasn't been processed yet when the rule fires).

## Cross-check: consistent patterns in the file

- CSB-09-001 (enter CS.V): `"Vfd..."` — V uppercase ✓
- CSB-12-001 (enter CS.P): `"...P.."` — P uppercase ✓
- CSB-13-001 (enter CS.X, pX→PX): `"...pX."` — X uppercase, P lowercase ✓
- CSB-13-002 (enter CS.X, embargo teardown): `"...PX."` — both P and X uppercase ✓
- CSB-14-002 (enter CS.A, trigger CS→P): `"...p.A"` — A uppercase, P lowercase ✓

**Promoted**: 2026-07-20 — pattern already captured inline in `specs/cs-behavior.yaml`
CSB-13-001 rationale (no new docs needed; archiving learning).
Docs PR: <!-- filled in after PR opens -->
