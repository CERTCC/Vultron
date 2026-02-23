# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate 
insights, issues, and learnings during the implementation process.

## 2026-02-20 — "Accept the offer" model/doc fixes

Corrected a systematic inconsistency where Accept/Reject responses were
modelled with `object=<offered-thing>` + `in_reply_to=<offer>`. The correct
ActivityStreams pattern is `object=<offer>` (you accept/reject the offer
activity itself, not what was offered).

### What changed

**Models** (`vultron/as_vocab/activities/case.py`):
- `RmInviteToCase`: `as_object` re-typed from `VulnerabilityCaseRef` →
  `as_ActorRef` (actor being invited); added `target: VulnerabilityCaseRef`.
- `RmAcceptInviteToCase`: dropped redundant `in_reply_to`; added
  `as_object: RmInviteToCaseRef`.
- `RmRejectInviteToCase`: same fix as Accept.
- `AcceptCaseOwnershipTransfer`: `as_object` re-typed to
  `OfferCaseOwnershipTransfer | str | None`; removed redundant `in_reply_to`.
- `RejectCaseOwnershipTransfer`: same fix as Accept.

**Vocab examples** (`vultron/scripts/vocab_examples.py`):
- `accept_invite_to_case()` / `reject_invite_to_case()`: `object` is now
  the `RmInviteToCase` activity; `in_reply_to` removed.
- `accept_case_ownership_transfer()` / `reject_case_ownership_transfer()`:
  `object` is now the `OfferCaseOwnershipTransfer` activity; `origin` removed.

**Docs** (sequence diagrams updated):
- `invite_actor.md`: `Accept(object=Invite)` / `Reject(object=Invite)`;
  `Invite` now shows full signature `Invite(actor=CaseOwner, object=Actor,
  target=Case)`.
- `transfer_ownership.md`: `Accept(object=Offer)` / `Reject(object=Offer)`.
- `suggest_actor.md`: same pattern for the inner Invite/Accept/Reject.

**Tests**: updated `test_vocab_examples.py` assertions to match new structure.

### Deferred: embargo Accept/Reject

`EmAcceptEmbargo` and `EmRejectEmbargo` in `embargo.py` have the same issue:
`as_object: EmbargoEventRef` should become `as_object: EmProposeEmbargoRef`.
The embargo flow also involves `ChoosePreferredEmbargo` (a Question type),
making the semantics more nuanced. Deferring to BT-5 implementation.

---

## 2026-02-20 — Bug fix: `VulnerabilityCase.set_embargo()` (BUGS.md HIGH priority)

Added `current_status` property to `VulnerabilityCase` returning the most-recent
`CaseStatus` (sorted by `updated` timestamp). Fixed `set_embargo()` to call
`self.current_status.em_state = EM.ACTIVE` instead of the broken
`self.case_status.em_state = EM.ACTIVE` (list attribute set). Added 6 tests in
`test/as_vocab/test_vulnerability_case.py`. All 492 tests pass.

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

**Handler inventory (17 done / 19 stubs)**:

Done:
- Report: create_report, submit_report, validate_report (BT), invalidate_report,
  ack_report, close_report, engage_case (BT), defer_case (BT)
- Case: create_case (BT), add_report_to_case, close_case, create_case_participant,
  add_case_participant_to_case
- Actor invitation: invite_actor_to_case, accept_invite_actor_to_case,
  reject_invite_actor_to_case, remove_case_participant_from_case

Stub (19 remaining):
- offer_case_ownership_transfer, accept_case_ownership_transfer,
  reject_case_ownership_transfer
- suggest_actor_to_case, accept_suggest_actor_to_case, reject_suggest_actor_to_case
- create_embargo_event, add_embargo_event_to_case, remove_embargo_event_from_case,
  announce_embargo_event_to_case
- invite_to_embargo_on_case, accept_invite_to_embargo_on_case,
  reject_invite_to_embargo_on_case
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
transitions.py). The EM state machine (NO_EMBARGO → PROPOSED → ACTIVE → REVISE → EXITED)
maps to the establish_embargo workflow. Note: `Accept` is an **activity
type** causing PROPOSED→ACTIVE (or REVISE→ACTIVE), not a state name.
Remember: EM state updates MUST go to
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

### Test count maintenance note

It's a waste of effort to maintain test counts in multiple files. It just 
makes for more work to update them and they can easily get out of sync.

---

### CaseStatus and ParticipantStatus ordering and interpretation

In a `VulnerabilityCase`, the `case_status` field is intended to be an 
append-only 
list of `CaseStatus` objects that represent the history of status changes to 
the case. The most recent `case_status` is the one with the latest updated 
timestamp. Items may arrive out of order, so sorting
by timestamp is necessary to determine the current status. It is an error for
updates to arrive from the future.

Similarly for `CaseParticipant` and `ParticipantStatus`.

Also note that a `ParticipantStatus` can include a `CaseStatus` object which 
is to 
be interpreted as the participant's view of the case status.
For example, a participant might be reporting that they are aware of attacks 
related to the vulnerability, which would be a participant status update that
includes a case status update that reflects the participant's view of the case
status as being in the ATTACKS_OBSERVED state.
The `CaseActor` 
might decide to update the `CaseStatus` based on a participant's view of the 
case, whether automatically or by prompting the case owner to review the status
update for approval before applying it to the case.

---

This note should update AGENTS.md and likely either a spec/*.md or notes/*.
md file for future reference.
Although AGENTS.md currently says to use lazy imports to avoid circular 
dependencies, 
in practice we should prefer to make imports at the module level and only use
lazy (local) imports when we actually encounter circular import issues. 
Using module level imports makes it easier to understand the dependencies of 
the module and is more consistent with typical Python coding practices.

When 
you encounter local imports, it's a code smell that there may be circular 
dependencies that need to be refactored. Try to refactor the code to use 
module-level imports and only keep the minimal local imports necessary to 
break circular dependencies when refactoring is not possible or practical.
If you encounter local imports while modifying code, it's okay to refactor
to use module level imports and fix any circular dependencies as part of the same change,
but avoid introducing new local imports without trying to refactor to module level imports first.

---
