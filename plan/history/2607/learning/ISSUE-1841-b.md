---
title: EmitAddCaseStatusToSelfNode CaseStatus extraction from ParticipantStatus
type: learning
timestamp: 2026-07-30T00:00:00Z
source: ISSUE-1841-b
signal: spec-ambiguity
---

RSH-01-003 specifies that `EmitAddCaseStatusToSelfNode` should emit a self-addressed
`Add(CaseStatus)` after `StatusUpdateGuard` passes, but does not specify how to
obtain the `CaseStatus` ID when only a `ParticipantStatus` ID is available in
`add_participant_status_tree`.

The implemented pattern:

1. Read `ParticipantStatus` from DataLayer using `participant_status_id`
2. Extract the embedded `.case_status` field (a `CaseStatus` object)
3. Persist the `CaseStatus` idempotently via `datalayer.create()` (catch `ValueError`)
4. Use `case_status.id_` when calling `trigger_activity_factory.add_case_status_to_case()`

This pattern relies on `ParticipantStatus.case_status` being populated at the time
`EmitAddCaseStatusToSelfNode` runs. If the field is `None`, the node returns FAILURE.
The spec should be updated to explicitly state that `CaseStatus` is extracted from the
embedded field of the `ParticipantStatus` record.

**Promoted**: 2026-07-31 — captured in `specs/received-status-handling.yaml` RSH-01-003 notes field.
Docs PR: TBD.
