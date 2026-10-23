---
source: NOTES-structured-logging--missing-info-messages
timestamp: '2026-09-17T17:32:55.535279+00:00'
title: Missing INFO Messages to Add (SL-04-001 violations)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered (PR #1988)
**Superseded by:** log lines added; SL-04-001

---

## Missing INFO Messages to Add (SL-04-001 violations)

These state transitions happened with no INFO output as of CONCERN-1968.
All of these are implemented as of #1988; the "Location" column records where
each line is emitted from.

| Domain | Message to add | Location |
|---|---|---|
| RM per-participant | `Actor '<id>' RM: <A> → <B> for case '<case_id>'` | `update_participant_rm_state()` **and** `CreateParticipantStatusNode` — the two per-participant RM write paths |
| CS/VFD | `Actor '<id>' CS: <vfd_before> → <vfd_after> (<event>) for case '<case_id>'` | `CreateParticipantStatusNode` (shared writer for fix-ready / fix-deployed) |
| CS/PXA | `Actor '<id>' CS: <pxa_before> → <pxa_after> (<event>) for case '<case_id>'` | `CreateParticipantStatusNode` (same node, PXA branch) |
| Case engagement | `Actor '<id>' engaged case '<case_id>' (RM VALID → ACCEPTED)` | `SvcEngageCaseUseCase._handle_result()` |
| EM PROPOSED→ACTIVE | `Actor '<id>' embargo PROPOSED → ACTIVE for case '<case_id>'` | `SetEmbargoActiveNode._apply_transition()` |
| EM ACTIVE→EXITED | `Actor '<id>' embargo ACTIVE → EXITED for case '<case_id>'` | `ClearActiveEmbargoNode`, `ApplyEmbargoTeardownNode` |
| Invite receipt | `Actor '<id>' received case invite for '<case_id>' from '<sender>'` | `InviteActorToCaseReceivedUseCase` (invitee path) |
| BT FAILURE reason | folded into the existing `BT execution completed: <status> after <N> ticks - <reason>` line | `BTBridge.execute_tree` (FAILURE path) |

The EM terminal state is spelled **EXITED** (`EM.EXITED`), not "TERMINATED":
the trigger is named `terminate` but the resulting state is `EXITED`.

The BT-failure row is deliberately *not* a separate narrative line. `BTBridge`
folds `get_failure_reason()` into the record it already emits, because a second
line would double-log, would fire for the many callers that treat `FAILURE` as
an expected idempotent skip (and log their own reason at DEBUG), and has no
reliable `case_id`: no production `execute_with_setup` call site passes one.
See the closing `NOTE` in `narrative_log.py`.

---
