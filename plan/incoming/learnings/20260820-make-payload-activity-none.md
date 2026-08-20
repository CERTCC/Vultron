---
title: "make_payload fixture leaves event.activity=None — ledger-commit tests must attach it manually"
type: learning
timestamp: 2026-08-20
source: ISSUE-2254
signal: concern
---

The `make_payload` fixture in `test/core/behaviors/status/conftest.py` calls
`extract_event(activity)` which returns a domain event with `event.activity = None`.
In production, the inbox pipeline sets `event.activity` to the raw AS2 activity object
before dispatching — unit tests that bypass the inbox never get this assignment.

`CommitCaseLedgerEntryNode` (via `_extract_payload_snapshot`) tries `getattr(activity, "activity", None)`.
When that is `None`, it falls back to dumping the domain event directly, which does not have
an `actor` key in its wire representation — causing `payloadSnapshot.actor must be a non-empty URI`.

**Workaround used in ISSUE-2254 tests:**

```python
event = make_payload(activity).model_copy(update={"activity": activity})
```

**Risk:** Any future test that exercises the ledger-commit path without attaching the raw activity
will fail with a confusing `payloadSnapshot.actor` error, not an obvious `activity is None` error.

**Root cause confirmed (ISSUE-2254 / PR #2421):** The `ADD_CASE_STATUS_TO_CASE` semantic registry
entry was missing `include_activity=True`. That flag causes `extract_intent()` to populate
`event.activity` with a `VultronActivity` snapshot of the raw AS2 activity. Without it, the inbox
never set `event.activity`, so `_extract_payload_snapshot` fell back to dumping the domain event
directly — which lacks the wire-format `actor` and `type` fields the ledger schema requires.

Fix applied: `include_activity=True` added to `semantic_registry/status.py` for
`ADD_CASE_STATUS_TO_CASE`. Compare: `ADD_PARTICIPANT_STATUS_TO_PARTICIPANT` already had it.

`_extract_payload_snapshot` also received a defensive `actor` patch from `actor_id` (lifecycle.py)
to guard against future callers that pass a domain event with `activity=None`.
