---
source: NOTES-bt-integration--rm-state-machine-participant-specific-context
timestamp: '2026-10-12T19:35:43.082437+00:00'
title: 'RM State Machine: Participant-Specific Context'
type: note
---

**Archived:** 2026-10-12
**Reason:** rewritten: the section described the superseded ADR-0015 flow and the removed ReportStatus layer; the lasting rule (RM is per participant) is kept in the note
**Superseded by:** ADR-0041; notes/case-proposal.md; notes/bt-integration.md

---

## RM State Machine: Participant-Specific Context

RM is a **participant-specific** state machine — each `CaseParticipant`
carries its own RM state in `participant_status[].rm_state`, independently
of other participants.

Per ADR-0015, a `VulnerabilityCase` is created at report receipt
(RM.RECEIVED). `CaseParticipant` records are created at that time:
reporter at RM.ACCEPTED, receiver at RM.RECEIVED. RM state is tracked
in `CaseParticipant.participant_status[].rm_state` from the moment
of case creation.

> **ADR-0015 is superseded by ADR-0041.** In the CASE_MANAGER-authoritative model
> the report receiver's tree no longer creates the `VulnerabilityCase` directly.
> The report receiver stores the report, writes a pending `VultronReportCaseLink`,
> and sends `Create(as_CaseProposal)` to the CASE_MANAGER; the CASE_MANAGER
> creates the case, adds participants, and initializes embargo before emitting
> `Create(VulnerabilityCase)` back to the report receiver, which becomes the
> CASE_OWNER.  See `notes/case-proposal.md`
> for the corrected flow (CM-22, CP-09).

`ReportStatus` in the flat status layer is a **transient pre-case
mechanism** that was previously used for reports not yet associated with
a case (pre-case RM states: RECEIVED, INVALID). Under ADR-0015, the case
is created at receipt, so `CaseParticipant` records carry RM state
from the start. `ReportStatus` is retained for backwards compatibility but
is no longer the primary RM state carrier.

This distinction affects how `engage_case` / `defer_case` handlers work:
they update participant-level RM state, not flat report status.
