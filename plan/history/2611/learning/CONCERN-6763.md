---
source: CONCERN-6763
timestamp: '2026-11-20T15:29:46.136841+00:00'
title: ParticipantStatus.case_engagement has no writer and repeats derived entitlement
type: learning
---

Theme: theme:wire-delivery — the `caseEngagement` key either gets a writer and survives each status, or stops travelling on the wire.

## Summary

`ParticipantStatus.case_engagement` (wire `caseEngagement`, default `True`) is a self-reported claim that no trigger, node or message ever sets. `CreateParticipantStatusNode` builds each new status without it, so any value but the default would be lost on the participant's next status. Planning #6748 found this: `tracking_id` had the same gap.

## Surface Symptom vs. Underlying Problem

The surface reading is "a field is missing a setter". The underlying question is whether "engaged" means anything apart from the participant's RM state. `Engage` already moves RM to ACCEPTED, and `Defer` moves it to DEFERRED. If the flag repeats what RM says, it is a dead duplicate and should be deleted, as #6415 deleted `participantCaseName`. If it means something else (for example "still watching but not acting"), it needs a spec, a writer and the same carry-forward rule CM-35-004 gives tracking IDs.

## Category

- [x] Technical debt

## Severity

Low

## Evidence

- `vultron/core/models/participant_status.py` (`case_engagement` field)
- `vultron/core/behaviors/case/nodes/participant/status.py` (`_build_status` does not pass it)
- `vultron/core/use_cases/triggers/case/engage.py` (moves RM only)

## Impact if Ignored

A wire key that always reads `true` suggests a meaning no implementation gives it. Another implementation that sets it to `false` would see the value dropped on its next status.

## Suggested Action

Decide whether engagement is anything apart from RM. If not, delete the field and its JSON-LD term (as #6415 did). If it is, specify it and carry it forward through the shared status-write helper #6762 adds.

Where: vultron/core/models/participant_status.py


**Resolved**: 2026-11-20 — implementation tracked in #6766. Decision: delete the field. Whether a participant is sent case content is derived from joined, not removed, a signatory of the active embargo (PEC row AGREED) when one is in force, and not at RM CLOSED (CM-10-004, CM-23-004).
Docs PR: https://github.com/CERTCC/Vultron/pull/6765.
Notes: `notes/case-communication-model.md`.
