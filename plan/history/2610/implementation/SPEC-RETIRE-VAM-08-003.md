---
source: SPEC-RETIRE-VAM-08-003
timestamp: '2026-10-14T19:44:43.761022+00:00'
title: Retired requirement VAM-08-003
type: implementation
---

Retired VAM-08-003 from `specs/vultron-as2-mapping.yaml` (#4598).

Why: CREATE_PARTICIPANT_STATUS no longer exists: the received Create(ParticipantStatus) stored the status with no ledger entry, so #4598 removed the route. This implementation does not support a separate Create(ParticipantStatus); the status travels inline on Add(ParticipantStatus) (VAM-08-004). Whether the protocol should support it is open question #4635.

Replacement: CLP-07-013

Final text: `plan/retired-specs/VAM-08-003.md`.
