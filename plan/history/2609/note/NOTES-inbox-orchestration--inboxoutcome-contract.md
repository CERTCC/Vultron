---
source: NOTES-inbox-orchestration--inboxoutcome-contract
timestamp: '2026-09-17T17:25:23.015343+00:00'
title: InboxOutcome Contract
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) in models.py + IO-01-001..004
**Superseded by:** specs/inbox-orchestration.yaml IO-01

---

## InboxOutcome Contract

`InboxOutcome` is a Pydantic model returned by every `process_payload` call:

```python
class InboxOutcome(BaseModel):
    status: Literal["processed", "deferred", "rejected"]
    context_id: str | None = None
    failure_reason: str | None = None
```

- `processed` — activity was dispatched successfully.
- `deferred` — activity was queued for replay (case context not yet known).
- `rejected` — activity could not be processed (parse failure, unknown type,
  or protocol violation). `failure_reason` is always populated for `rejected`
  outcomes.

`process_payload` MUST NOT raise for protocol-invalid payloads. All error
conditions produce a typed `rejected` outcome with an explicit
`failure_reason`. Callers use the outcome status to decide logging severity
and response codes.

---
