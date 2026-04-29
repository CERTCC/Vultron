---
title: "PRIORITY-310 \u2014 D5-6-LOG, D5-6-STATE, D5-6-STORE, D5-6-WORKFLOW"
type: implementation
date: '2026-04-06'
source: PRIORITY-310
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 4722
legacy_heading: "Phase PRIORITY-310 \u2014 D5-6-LOG, D5-6-STATE, D5-6-STORE,\
  \ D5-6-WORKFLOW (COMPLETE 2026-04-06)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-06'
---

## PRIORITY-310 — D5-6-LOG, D5-6-STATE, D5-6-STORE, D5-6-WORKFLOW

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:4722`
**Canonical date**: 2026-04-06 (git blame)
**Legacy heading**

```text
Phase PRIORITY-310 — D5-6-LOG, D5-6-STATE, D5-6-STORE, D5-6-WORKFLOW (COMPLETE 2026-04-06)
```

**Legacy heading dates**: 2026-04-06

These four tasks addressed reviewer feedback D5-6a–h from
`notes/two-actor-feedback.md`. All four were completed and validated
(black/flake8/mypy/pyright/pytest clean) as of 2026-04-06.

### D5-6-LOG — Improve process-flow logging across demo containers

Improved INFO-level logging so container logs tell a coherent process-flow
story (D5-6a, b, e, f, g):

- Added INFO log entries to finder actor for outgoing activity creation (report
  creation, OfferReport submission) so finder actions visible in combined log.
- Formatted "Parsing activity from request body" entries as multiline indented
  JSON.
- Added INFO-level logs throughout vendor BT sequences: RM state transitions,
  case creation steps, embargo initialization.
- Added INFO-level logs for participant record actions: creation, status record
  creation (with role and status values), and attachment to case.
- Verified combined container logs allow following full process flow.

### D5-6-STATE — Clarify RM state log messages; initialize finder participant

Fixed RM state transition log clarity and finder initial state (D5-6c):

- Updated RM state transition logs to explicitly identify which actor's state
  is changing (e.g., "Vendor RM: START → RECEIVED" vs "Finder RM: ACCEPTED").
- When vendor receives submitted report, creates CaseParticipant status record
  for finder initialized to RM.ACCEPTED (finder must be at RM.ACCEPTED to
  submit).

### D5-6-STORE — Verify datalayer reference storage for nested objects

Investigated and confirmed datalayer stores nested objects by reference (D5-6d):

- Confirmed TinyDB adapter stores activities with nested objects serialized
  inline at save time, but the use-case code constructs activities with ID
  references where appropriate.
- Updated demo-runner log messages to clarify rehydrated views vs stored
  references.
- Added datalayer tests confirming transitive activities use ID references.

### D5-6-WORKFLOW — Automate complete case creation from validate-report

Refactored validate-report BT to execute complete case creation as single
automated sequence (D5-6h). The 7-node ValidationActions sequence:

1. TransitionRMtoValid — vendor RM → VALID
2. CreateCaseNode — creates VulnerabilityCase with report reference
3. InitializeDefaultEmbargoNode — creates embargo + AnnounceEmbargo activity
4. CreateInitialVendorParticipant — vendor participant, RM → ACCEPTED
5. CreateFinderParticipantNode — finder participant + Add notification
6. CreateCaseActivity — generates CreateCaseActivity for notification
7. UpdateActorOutbox — queues activities to vendor's outbox

Removed manual engage-case and add-finder-participant steps from two-actor
demo. Updated tests to verify full automated workflow.
