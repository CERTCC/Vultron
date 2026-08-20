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

**Possible fix:** Update `_extract_payload_snapshot` to fall back to `event.actor_id` when
`activity.activity` is None and `activity` is a domain event. Or update the `make_payload`
fixture to always attach `event.activity`. Track as a follow-up Concern.
