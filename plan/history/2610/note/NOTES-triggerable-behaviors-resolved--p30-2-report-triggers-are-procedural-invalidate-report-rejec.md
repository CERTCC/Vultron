---
source: NOTES-triggerable-behaviors-resolved--p30-2-report-triggers-are-procedural-invalidate-report-rejec
timestamp: '2026-10-02T16:28:28.817625+00:00'
title: 'P30-2: Report Triggers are Procedural (invalidate-report, reject-report)'
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered/confusion-resolved — invalidate-report and reject-report are now BT-backed (create_invalidate_report_trigger_tree, create_reject_report_trigger_tree); _add_activity_to_outbox no longer exists
**Superseded by:** vultron/core/behaviors/report/trigger_report_trees.py

---

## P30-2: Report Triggers are Procedural (invalidate-report, reject-report)

`invalidate-report` and `reject-report` are implemented procedurally, not
as BT trees. Per AGENTS.md guidance, simple linear workflows with no
branching SHOULD use procedural code.

- `invalidate-report`: Creates `RmInvalidateReport` (TentativeReject) directly.
- `reject-report`: Creates `RmCloseReport` (Reject) directly; requires a
  non-empty `note` field (TRIG-03-004).

**Shared helper**: `_add_activity_to_outbox()` was extracted to DRY up the
outbox-append pattern across multiple trigger endpoints (avoids repeating the
same DataLayer read → append → write sequence).

**`reject-report` `note` field semantics**: The spec says the value SHOULD be
non-empty (not MUST). An empty `note` string logs a WARNING but is accepted.
This is enforced via a `@field_validator` on `RejectReportRequest.note` rather
than a `NonEmptyString` type, because the rule is advisory (SHOULD), not
mandatory (MUST).
