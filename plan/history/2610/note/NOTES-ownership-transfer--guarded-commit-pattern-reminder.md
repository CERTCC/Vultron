---
source: NOTES-ownership-transfer--guarded-commit-pattern-reminder
timestamp: '2026-10-12T19:35:17.539654+00:00'
title: Guarded-Commit Pattern Reminder
type: note
---

**Archived:** 2026-10-12
**Reason:** stale code sketch ('once routing is corrected'); the receive-tree factory injects the guarded commit
**Superseded by:** CLP-09-001; notes/case-communication-model.md; vultron/core/behaviors/case/

---

## Guarded-Commit Pattern Reminder

`AcceptCaseOwnershipTransferReceivedUseCase` is a **received-side** use case.
Both the CASE_MANAGER and participant replicas may receive the same Accept
activity (once routing is corrected). The guarded-commit ensures only the
CASE_MANAGER writes the ledger entry:

```python
if request.receiving_actor_id != case_actor_id:
    return  # not the CASE_MANAGER — skip commit
```

See `notes/case-communication-model.md` § "Antipattern: Received-Side
Guarded Commit with Foreign CASE_MANAGER ID" for the full pattern.
