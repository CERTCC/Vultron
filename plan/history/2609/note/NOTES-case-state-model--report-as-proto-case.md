---
source: NOTES-case-state-model--report-as-proto-case
timestamp: '2026-09-17T17:13:53.842174+00:00'
title: 'Report as Proto-Case: Finder Participant Lifecycle'
type: note
---

**Archived:** 2026-09-17
**Reason:** (e) 'Implemented Lifecycle (per ADR-0015)' superseded by ADR-0041 (receiver holds no interim case); caterpillar/butterfly metaphor retained inline
**Superseded by:** ADR-0041; notes/case-bootstrap-trust.md § ADR-0041 Update

---

## Report as Proto-Case: Finder Participant Lifecycle

> **Status**: The FINDER-PART-1 approach described in the original version
> of this section has been **superseded** by ADR-0015 (Create
> VulnerabilityCase at Report Receipt). The new lifecycle is documented
> below.

The lifecycle of CVD work begins with a *report*, and the Vultron model
reflects this by creating a `VulnerabilityCase` immediately when an
`Offer(Report)` is received. A useful analogy is the caterpillar/butterfly
metamorphosis:

- **Caterpillar stage** = case object in RM.RECEIVED or RM.INVALID
  (the case exists but has not yet been validated; participants are
  active but the vendor has not yet committed to the issue)
- **Butterfly stage** = case object in RM.VALID, RM.ACCEPTED, or
  RM.DEFERRED (the case is validated and actionable)
- **Terminal** = RM.CLOSED (regardless of path)

Work genuinely happens in both stages, and participants exist in both.

### Redefined "Proto-Case"

A **proto-case** is a `VulnerabilityCase` object that is in the caterpillar
stage — the case object exists (and has been created at report receipt),
but the receiver has not yet validated the report. RM states RM.RECEIVED
and RM.INVALID are proto-case stages.

This is a redefinition from the earlier concept where "proto-case" meant
the state *before* a case object existed. Under ADR-0015, a case object
always exists from the moment a report is received, so the pre-case-object
era is eliminated.

### Implemented Lifecycle (per ADR-0015)

1. Reporter submits `Offer(Report)` → `SubmitReportReceivedUseCase`
   invokes the `receive_report_case_tree` BT, which:
   - Creates a `VulnerabilityCase` with `vulnerability_reports` linking
     to the `VulnerabilityReport` ID
   - Creates a `VultronParticipant` for the reporter with
     `rm_state=RM.ACCEPTED` (they created and submitted the report)
   - Creates a `VultronParticipant` for the receiver with
     `rm_state=RM.RECEIVED`
   - Initializes a default embargo (SHOULD; MUST before RM.VALID)
   - Queues a `Create(Case)` activity to notify the reporter
2. Receiver runs the `ValidateReport` BT:
   - Evaluates report credibility and validity
   - Transitions RM to RM.VALID (or RM.INVALID if rejected)
   - Verifies that an embargo exists (`EnsureEmbargoExists` guard)
   - Does **not** create a case (the case already exists from step 1)
3. All subsequent report-centric activities (invalidate, close, validate)
   dereference the `report_id → case_id` and delegate to case-level use
   cases.

**No retroactive context migration is needed.** The `VultronParticipant`
records are created with `context` pointing to the `VulnerabilityCase` ID
from the start.

**See also**: `docs/adr/0015-create-case-at-report-receipt.md`;
`specs/case-management.yaml` CM-12; `notes/protocol-event-cascades.md`

---
