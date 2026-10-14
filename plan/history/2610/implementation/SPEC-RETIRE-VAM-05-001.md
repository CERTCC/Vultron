---
source: SPEC-RETIRE-VAM-05-001
timestamp: '2026-10-14T19:44:26.474606+00:00'
title: Retired requirement VAM-05-001
type: implementation
---

Retired VAM-05-001 from `specs/vultron-as2-mapping.yaml` (#4598).

Why: CREATE_EMBARGO_EVENT no longer exists: the received Create(EmbargoEvent) stored the event with no ledger entry, and nothing sent it, so #4598 removed the route. This implementation does not support a separate Create(Event); a proposal carries its EmbargoEvent inline on the Invite. Whether the protocol should support it is open question #4635.

Replacement: CLP-07-013

Final text: `plan/retired-specs/VAM-05-001.md`.
