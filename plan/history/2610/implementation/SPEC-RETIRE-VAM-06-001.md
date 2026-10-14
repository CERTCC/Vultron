---
source: SPEC-RETIRE-VAM-06-001
timestamp: '2026-10-14T19:44:31.848156+00:00'
title: Retired requirement VAM-06-001
type: implementation
---

Retired VAM-06-001 from `specs/vultron-as2-mapping.yaml` (#4598).

Why: CREATE_CASE_PARTICIPANT no longer exists as a received message: the direct Create(CaseParticipant) stored the record with no ledger entry, and nothing sent it, so #4598 removed the route. Create(CaseParticipant) survives as the snapshot of the CASE_MANAGER's create_case_participant ledger entry (CM-11-006). Whether the protocol should support a direct Create is open question #4635.

Replacement: CLP-07-013

Final text: `plan/retired-specs/VAM-06-001.md`.
