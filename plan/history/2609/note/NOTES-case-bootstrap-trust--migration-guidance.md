---
source: NOTES-case-bootstrap-trust--migration-guidance
timestamp: '2026-09-17T17:10:51.369715+00:00'
title: Migration Guidance (case bootstrap)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) ADR-0041 migration complete; in-file ADR-0041 Update section corrects it
**Superseded by:** vultron/core/behaviors/case/receive_report_case_tree.py; ADR-0041

---

## Migration Guidance

Per ADR-0041, the following call sites change:

1. **Case creation at report receipt** — receiver no longer creates
   `VulnerabilityCase`; replaced by `VultronReportCaseLink(status=PENDING_PROPOSAL)`
2. **CASE_MANAGER bootstrap payload** — `Create(VulnerabilityCase)` must embed
   inline participants (not bare IDs)
3. **Participant-side bootstrap validation and trust persistence** — already
   implemented in `CreateCaseReceivedUseCase`; no change needed
4. **Unknown-context / pre-bootstrap queueing** — existing queueing logic
   applies unchanged
5. **Invite-to-case handling for late-joiner trust establishment** — unchanged

---
