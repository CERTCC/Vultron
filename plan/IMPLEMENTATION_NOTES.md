# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate 
insights, issues, and learnings during the implementation process.

Append new notes below this line.

---

## 2026-02-20 — Gap Analysis Refresh #2 (PLAN_prompt.md run)

### Test status

486 passing, 5581 subtests passed, 0 xfailed (confirmed by running full suite).

### Bug: `VulnerabilityCase.set_embargo()` — silent no-op on em_state

`vultron/as_vocab/objects/vulnerability_case.py` line 100:
`self.case_status.em_state = EM.ACTIVE` — but `case_status` is
`list[CaseStatusRef]`. Setting `.em_state` on a plain Python list will raise
`AttributeError` at runtime (lists don't support arbitrary attribute
assignment). The fix is `self.case_status[0].em_state = EM.ACTIVE`. Logged in
`plan/BUGS.md`. **Must fix before implementing BT-5 embargo handlers.**

### Actor direction for invite handlers

Per the sequence diagram in `docs/howto/activitypub/activities/invite_actor.md`:

- **Case Owner → Actor**: `Invite(object=Case)` hits the **Actor's** inbox
  → `invite_actor_to_case` handler stores the invite for local consideration.
- **Actor → Case Owner**: `Accept(object=Case, inReplyTo=Invite)` hits the
  **Case Owner's** inbox → `accept_invite_actor_to_case` handler creates the
  `CaseParticipant`. **The participant creation logic lives in the accept
  handler, not the invite handler.**

This asymmetry is easy to miss. Each actor only sees their own inbox.

### VulnerabilityCase API for embargo handlers (BT-5 implementation notes)

`VulnerabilityCase` already provides:

- `active_embargo: EmbargoEventRef` — currently active embargo
- `proposed_embargoes: list[EmbargoEventRef]` — embargoes under negotiation
- `set_embargo(embargo)` — once bug is fixed, this is the right API to call
  for `add_embargo_event_to_case` / ActivateEmbargo

Handler-to-field mapping for BT-5:

| Handler                          | VulnerabilityCase mutation                               |
|----------------------------------|----------------------------------------------------------|
| `create_embargo_event`           | persist `EmbargoEvent` to DataLayer only                |
| `invite_to_embargo_on_case`      | append to `case.proposed_embargoes`, emit Invite        |
| `accept_invite_to_embargo_on_case` | call `case.set_embargo(embargo)` (after bug fix)      |
| `add_embargo_event_to_case`      | call `case.set_embargo(embargo)` (after bug fix)        |
| `remove_embargo_event_from_case` | `case.active_embargo = None`; update `em_state`         |
| `announce_embargo_event_to_case` | emit `as:Announce(EmbargoEvent)` to all participants    |
| `reject_invite_to_embargo_on_case` | log, optionally remove from `proposed_embargoes`      |

EM state transitions (CM-04-003): MUST update `CaseStatus.em_state`, NOT
`ParticipantStatus`. Use `case.case_status[0].em_state` (or the fixed
`set_embargo()` helper).

### Embargo state machine reminder

`EM` enum (from `vultron/bt/embargo_management/states.py`):
`NO_EMBARGO → PROPOSED → ACTIVE` (aliases: N=NO_EMBARGO, P=PROPOSED, A=ACTIVE).
Update `case_status[0].em_state` at each transition.
Note: There is no explicit "ACCEPTED" state in the enum — acceptance triggers
the `ACTIVE` transition directly.

---



### Current state after BT-3 and BT-4.2 completion

486 tests passing, 0 xfailed. The previously-xfailed reporting workflow tests
were rewritten in commit `fix: rewrite xfail reporting workflow tests for
current handlers`.

**Handler inventory (13 done / 23 stubs)**:

Done:
- Report: create_report, submit_report, validate_report (BT), invalidate_report,
  ack_report, close_report, engage_case (BT), defer_case (BT)
- Case: create_case (BT), add_report_to_case, close_case, create_case_participant,
  add_case_participant_to_case

Stub (23 remaining):
- invite_actor_to_case, accept_invite_actor_to_case, reject_invite_actor_to_case
- offer_case_ownership_transfer, accept_case_ownership_transfer,
  reject_case_ownership_transfer
- suggest_actor_to_case, accept_suggest_actor_to_case, reject_suggest_actor_to_case
- create_embargo_event, add_embargo_event_to_case, remove_embargo_event_from_case,
  announce_embargo_event_to_case
- invite_to_embargo_on_case, accept_invite_to_embargo_on_case,
  reject_invite_to_embargo_on_case
- remove_case_participant_from_case
- create_note, add_note_to_case, remove_note_from_case
- create_case_status, add_case_status_to_case, create_participant_status,
  add_participant_status_to_participant

### Next implementation priorities

**BT-4.1** is the highest-priority gap: the actor invitation trio
(`invite_actor_to_case`, `accept_invite_actor_to_case`,
`reject_invite_actor_to_case`) and `remove_case_participant_from_case`. These
are needed to complete the `invite_actor_demo.py` script (BT-4.3).

**Design guidance for BT-4.1**:
- `invite_actor_to_case`: Store Invite activity, emit `as:Invite(VulnerabilityCase)`
  to target actor inbox. Simple procedural — no BT needed.
- `accept_invite_actor_to_case`: Create `CaseParticipant`, persist, notify case
  owner via outbox. Moderate complexity — consider BT.
- `reject_invite_actor_to_case`: Log rejection, optionally notify inviter.
  Simple procedural.
- `remove_case_participant_from_case`: Remove participant from case, persist.
  Simple procedural with idempotency guard.

**BT-5 (embargo)** follows. The simulation reference is
`vultron/bt/embargo_management/` (behaviors.py, conditions.py, states.py,
transitions.py). The EM state machine (NONE → PROPOSED → ACCEPTED → ACTIVE)
maps to the establish_embargo workflow. Remember: EM state updates MUST go to
`CaseStatus.em_state` (participant-agnostic), NOT to `ParticipantStatus` —
CM-04-003.

### Idempotency pattern reminder

For new handlers that change RM/EM/CS state (ID-04-004 MUST):
Use the same Selector pattern from validate_report and prioritize_tree:
`Selector(CheckAlreadyInTargetState, TransitionSequence)`. This provides the
idempotency early-exit without extra conditional code in the handler.

### Demo script architecture note

New demo scripts should call `initialize_case_demo.py` setup functions as
preconditions rather than duplicating setup logic. The `initialize_case_demo.py`
creates actor, submits report, validates it, and creates a case — this is the
baseline precondition for all subsequent workflow demos.

---

It's a waste of effort to maintain test counts in multiple files. It just 
makes for more work to update them and they can easily get out of sync.

---
