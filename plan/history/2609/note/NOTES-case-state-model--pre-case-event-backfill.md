---
source: NOTES-case-state-model--pre-case-event-backfill
timestamp: '2026-09-17T17:13:53.597332+00:00'
title: Pre-Case Event Backfill on Case Creation
type: note
---

**Archived:** 2026-09-17
**Reason:** (e) ADR-0015 flow superseded by ADR-0041
**Superseded by:** ADR-0041; notes/case-proposal.md

---

## Pre-Case Event Backfill on Case Creation

> **Note**: Under ADR-0015, the case is created at report receipt, so
> backfill is minimal. The `Offer(Report)` activity IS the case-creation
> trigger; participant creation happens atomically in the same BT.

When a new case is created via `receive_report_case_tree`, the following
events are recorded in the case ledger as part of that BT's execution:

- Case creation itself
- Initial participant creation (reporter and receiver)
- Default embargo initialization (if applied)
- `Create(Case)` notification queued to outbox

Events that predate the case object cannot exist in the new model (the
case is created at the first opportunity). If pre-case events were recorded
via a separate mechanism (e.g., a flat `ReportStatus`), those MAY be
backfilled into the case ledger at case creation time.

**See**: `specs/case-management.yaml` CM-12; `notes/activitystreams-semantics.md`
for the case activity log constraints.

---
