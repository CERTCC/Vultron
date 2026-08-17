---
title: "py_trees blackboard is process-global and survives BT runs; every guard→effect handoff must be written per tick and ID-matched"
type: learning
timestamp: "2026-08-12T00:00:00Z"
source: ISSUE-2235
signal: concern
---

The ISSUE-2235 fix needed a read-only precondition guard
(`FilterParticipantStatusDimensionsNode`) to hand a filtered `ParticipantStatus`
to two downstream consumers in the same tree. The only available channel is the
py_trees blackboard, and it is a **process-global singleton**. `BTBridge.execute_with_setup`
restores exactly two keys between runs — `datalayer` and `trigger_activity_factory`
— so every other key written by a previous BT execution is still visible to the
next one, in the same process.

Consequences observed while implementing:

- A guard that writes its key *only when it has something to say* leaks that
  value into the next activity's tree, where a consumer reads a stale payload
  that describes a different object entirely. The fix is to write the key on
  **every** tick, with `None` when there is nothing to publish.
- Writing per tick is not sufficient on its own: two activities in the same
  process can carry different object IDs, so the payload must also record which
  object it applies to and consumers must **ID-match** before honouring it.
  Both new keys (`append_status_dimension_filter`,
  `ledger_payload_object_override`) carry the ID and are matched on read.

This is not specific to this fix. Any future guard→effect blackboard handoff has
the same hazard, and the failure mode is silent cross-activity contamination
that unit tests running one tree per process will not reproduce. Candidates for
a systemic fix: have `BTBridge` clear (or namespace per-execution) all keys it
did not explicitly seed, rather than restoring a hardcoded pair.

**Promoted**: 2026-08-17 — captured in AGENTS.md pitfall: py_trees blackboard is process-global.
Docs PR: TBD.
