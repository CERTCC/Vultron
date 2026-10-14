---
source: NOTES-case-proposal--implementation-vultronaccept-result
timestamp: '2026-10-12T19:33:12.066259+00:00'
title: 'Implementation: VultronAccept.result'
type: note
---

**Archived:** 2026-10-12
**Reason:** copy of live code
**Superseded by:** vultron/core/models/activity.py; EmitAcceptCaseProposalNode

---

## Implementation: `VultronAccept.result`

`vultron.core.models.activity.VultronAccept` carries a `result: str | None`
field. `EmitAcceptCaseProposalNode` reads `case_id` from the py\_trees
blackboard (written earlier by `LoadExistingCaseNode` or
`CreateCaseFromProposalNode`) and sets `result=case_id` on the activity
before persisting it to the DataLayer and outbox.
