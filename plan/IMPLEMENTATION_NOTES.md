## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

---

### 2026-04-07 Gap analysis observations (refresh #71)

**Test suite**: 1261 tests passing (up from 1247 in refresh #70). No
warnings, no ResourceWarnings. All linters clean.

**D5-6-CASEPROP partial fix confirmed** (code-verified): The
`CreateCaseActivity` node in `vultron/core/behaviors/report/nodes.py`
(validate-report BT) was updated in D5-6-DEMOAUDIT to include
`to=addressees` and embed the full `VulnerabilityCase` as `object_`. However,
`EmitCreateCaseActivity` in `vultron/core/behaviors/case/nodes.py`
(create-case BT) still lacks a `to` field and does not embed the full case
object. D5-6-CASEPROP should align these two nodes or consolidate them. The
three-actor demo's `actor_engages_case()` fix is blocked on D5-6-AUTOENG: once
auto-engagement works, the manual call is eliminated entirely.

**D5-6-AUTOENG blocks three-actor demo refactor**: The three-actor demo's
`actor_engages_case()` calls `engage-case` on `case_actor_client` (the
case-actor container) instead of the actor's own container. This will be
resolved by D5-6-AUTOENG (auto-engage after invite acceptance), which
eliminates the need for a manual call. D5-6-AUTOENG should be prioritised
before D5-6-CASEPROP's demo cleanup.

**D5-6-EMBARGORCP is independent of D5-6-AUTOENG**: The recommended fix
(remove standalone `Announce(embargo)` from validate-report BT; rely on
`Create(Case)` carrying `VulnerabilityCase.active_embargo`) is now viable
because D5-6-DEMOAUDIT fixed the `Create(Case)` activity to include the full
case object with `active_embargo` set. This task can be addressed in any order
relative to D5-6-AUTOENG.

**EMBARGO-DUR-1 is straightforward to implement**: `isodate>=0.7.2` is
already a declared dependency in `pyproject.toml`. The implementation only
requires changing `EmbargoPolicy` integer fields to `timedelta` + ISO 8601
serializer, and updating `InitializeDefaultEmbargoNode`'s policy lookup from
`preferred_duration_days` to `preferred_duration`. The `specs/duration.md`
reference implementation pattern can be applied directly.

**FINDER-PART-1 partial implementation exists**: `SubmitReportReceivedUseCase`
already creates a `VultronParticipantStatus` for the finder at report receipt
(with `rm_state=RM.ACCEPTED`). The full FINDER-PART-1 task requires creating a
`CaseParticipant` domain object with `context` pointing to the
`VulnerabilityReport` ID. An open design question in
`notes/case-state-model.md` ("Report as Proto-Case: Finder Participant
Lifecycle") — specifically whether the record belongs in `SubmitReportReceived`
or `CreateReportReceived`, and whether it should use the existing
`VultronParticipant` or a new `CaseParticipant` — must be resolved before
implementation proceeds.

**Suggested task ordering for PRIORITY-310 completion**:

1. D5-6-AUTOENG (auto-engage after invite; blocks D5-6-CASEPROP demo cleanup)
2. D5-6-EMBARGORCP (independent; remove standalone Announce from validate BT)
3. D5-6-NOTECAST (independent; broadcast notes to participants in AddNoteToCase)
4. D5-6-CASEPROP (EmitCreateCaseActivity `to` field; demo cleanup after AUTOENG)
5. D5-7 (human sign-off)

### 2026-04-08 D5-6-AUTOENG completion

**D5-6-AUTOENG completed**: `AcceptInviteActorToCaseReceivedUseCase` now
creates the participant, pre-seeds RM history, and immediately invokes
`SvcEngageCaseUseCase`, so invitation acceptance now advances the invitee to
RM.ACCEPTED and emits a queued `RmEngageCaseActivity` without a separate
trigger.

**Demo cleanup completed**: `vultron/demo/three_actor_demo.py` and
`vultron/demo/multi_vendor_demo.py` no longer issue manual `engage-case`
trigger calls after invite acceptance. This removes the protocol shortcut
identified in D5-6-DEMOAUDIT and leaves D5-6-CASEPROP focused only on
`CreateCaseActivity` propagation/addressing gaps.

**Testing note**: When tests need to persist actor records through
`DataLayer.create`, use a concrete actor subtype such as `as_Organization`
rather than the base `as_Actor`; the base type's optional `type_` conflicts
with the `PersistableModel` protocol under pyright.
