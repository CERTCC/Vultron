---
source: SPEC-RETIRE-VAM-08-001
timestamp: '2026-10-14T19:44:37.368997+00:00'
title: Retired requirement VAM-08-001
type: implementation
---

Retired VAM-08-001 from `specs/vultron-as2-mapping.yaml` (#4598).

Why: CREATE_CASE_STATUS no longer exists: the received Create(CaseStatus) stored the status with no ledger entry, so #4598 removed the route. This implementation does not support a separate Create(CaseStatus); the status travels inline on Add(CaseStatus) (VAM-08-002). Whether the protocol should support it is open question #4635.

Replacement: CLP-07-013

Final text: `plan/retired-specs/VAM-08-001.md`.
