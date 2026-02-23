# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate 
insights, issues, and learnings during the implementation process.

## 2026-02-24 — Phase BT-5 Complete

### 7 embargo handlers implemented

All 7 embargo management handlers are implemented in
`vultron/api/v2/backend/handlers.py`:

- `create_embargo_event` — stores a new `EmbargoEvent` in the DataLayer
- `add_embargo_event_to_case` — associates an embargo with a case, sets
  `active_embargo = embargo.as_id` and transitions `em_state` to `PROPOSED`
- `remove_embargo_event_from_case` — removes the active embargo from a case,
  transitions `em_state` back to `NONE`
- `announce_embargo_event_to_case` — logs receipt of the announcement; no
  case state change (see note below)
- `invite_to_embargo_on_case` — stores the invite activity in the DataLayer
- `accept_invite_to_embargo_on_case` — sets `active_embargo = embargo.as_id`
  and transitions `em_state` to `ACTIVE`
- `reject_invite_to_embargo_on_case` — stores the reject activity, no state
  change

### `establish_embargo_demo.py` created

Demo script at `vultron/scripts/establish_embargo_demo.py` demonstrates two
paths: propose-accept and propose-reject. Both paths pass
(`test/scripts/test_establish_embargo_demo.py`).

### BT-5 pre-condition fixes

Fixed `EmAcceptEmbargo` and `EmRejectEmbargo` in
`vultron/as_vocab/activities/embargo.py`:

- `as_object` type changed from `EmbargoEventRef` to `EmProposeEmbargoRef`
  (Accept/Reject respond to the *proposal activity*, not the proposed thing)
- `in_reply_to` fields removed (redundant with `as_object`)

Fixed 3 activity patterns in `vultron/activity_patterns.py`:
`InviteToEmbargoOnCase`, `AnnounceEmbargoEventToCase`,
`RemoveEmbargoEventFromCase`.

### `case_activity` list cannot store specific activity subtypes

`VulnerabilityCase.case_activity: list[as_Activity]` uses
`as_Activity.as_type: as_ObjectType`. The `as_ObjectType` enum only includes
core AS2 object types ('Activity', 'Note', 'Event', etc.) — NOT transitive
activity types like 'Announce', 'Add', 'Accept', etc.

Storing a specific-typed activity (e.g., `AnnounceEmbargo`) in `case_activity`
then serializing and reloading causes `model_validate` to fail with
`Input should be 'Activity', 'Actor', ...`, causing `record_to_object` to fall
back to a raw TinyDB `Document`. The handler's subsequent `dl.read(case.as_id)`
returns a `Document`, not a `VulnerabilityCase`, silently losing all state
(including `active_embargo`).

**Fix**: `announce_embargo_event_to_case` does NOT write to `case.case_activity`
— it only logs the announcement. Handlers that would modify case state
(add/remove/accept) store `embargo.as_id` (string) rather than the full object
to avoid the `active_embargo` Pydantic Union serialization issue.

### `active_embargo` must be stored as string ID

`VulnerabilityCase.active_embargo: EmbargoEvent | as_Link | str | None` —
Pydantic v2 serializes Union types left-to-right. If the value is an
`as_Event` (not `EmbargoEvent`) AND serialized with `by_alias=True`, Pydantic
silently returns `None`. `object_to_record` uses `model_dump(mode='json')`
(without `by_alias=True`), which works — but to be safe and avoid type
confusion, all embargo handlers store `embargo.as_id` (a string) rather than
the full object. `validate_by_name=True` in `VulnerabilityCase.model_config`
ensures the string round-trips correctly.


### `invite_actor_demo.py` created

`vultron/scripts/invite_actor_demo.py` implements two demo workflows:

1. **Accept path**: vendor invites coordinator → coordinator accepts →
   coordinator added as `CaseParticipant` to the case
2. **Reject path**: vendor invites coordinator → coordinator rejects →
   participant list unchanged

Test: `test/scripts/test_invite_actor_demo.py` mirrors
`test_initialize_case_demo.py`.

### Bug fixed: `InviteActorToCase` pattern

`InviteActorToCase` in `vultron/activity_patterns.py` used
`object_=AOtype.ACTOR` ("Actor") but real actors have type "Organization"
or "Person". This prevented semantic matching for invite/accept/reject
workflows when the invited actor was rehydrated from the datalayer.

Fix: removed `object_=AOtype.ACTOR` from `InviteActorToCase`. The pattern
now checks only `activity_=INVITE` and `target_=VULNERABILITY_CASE`, which
is sufficient to distinguish it from `InviteToEmbargoOnCase`
(`target_=EVENT`).

### Note: Accept/Reject activities should reference invite by ID

When constructing `RmAcceptInviteToCase` or `RmRejectInviteToCase`,
`object` should be the invite's ID string (not the full invite object
inline). Passing the full object inline causes it to be parsed as generic
`as_Object` during HTTP deserialization, losing the `actor` field, which
then fails `as_Invite` validation during rehydration. Using the ID allows
the handler to rehydrate the invite from the datalayer with all fields.

---

## 2026-02-23 — Gap Analysis Refresh #3 (PLAN_prompt.md run)

### Test status

497 passing, 5581 subtests passed, 0 xfailed (confirmed by running full suite).

### Handler inventory (17 done / 20 stubs)

**Done** (17 handlers with real business logic):
- Report: `create_report`, `submit_report`, `validate_report` (BT),
  `invalidate_report`, `ack_report`, `close_report`
- Case priority: `engage_case` (BT), `defer_case` (BT)
- Case: `create_case` (BT), `add_report_to_case`, `close_case`
- Participant CRUD: `create_case_participant`, `add_case_participant_to_case`
- Actor invitation (BT-4.1): `invite_actor_to_case`, `accept_invite_actor_to_case`,
  `reject_invite_actor_to_case`, `remove_case_participant_from_case`

**Stubs** (20 remaining — debug-log only):
- Ownership transfer: `offer_case_ownership_transfer`,
  `accept_case_ownership_transfer`, `reject_case_ownership_transfer`
- Suggest actor: `suggest_actor_to_case`, `accept_suggest_actor_to_case`,
  `reject_suggest_actor_to_case`
- Embargo core: `create_embargo_event`, `add_embargo_event_to_case`,
  `remove_embargo_event_from_case`, `announce_embargo_event_to_case`
- Embargo negotiation: `invite_to_embargo_on_case`,
  `accept_invite_to_embargo_on_case`, `reject_invite_to_embargo_on_case`
- Notes: `create_note`, `add_note_to_case`, `remove_note_from_case`
- Statuses: `create_case_status`, `add_case_status_to_case`,
  `create_participant_status`, `add_participant_status_to_participant`

### BT-5 Pre-condition: EmAcceptEmbargo / EmRejectEmbargo model fix

`EmAcceptEmbargo` and `EmRejectEmbargo` in
`vultron/as_vocab/activities/embargo.py` have incorrect `as_object` types:

- **Current**: `as_object: EmbargoEventRef` (the embargo event itself)
- **Correct**: `as_object: EmProposeEmbargoRef` (the invite/proposal activity)

Per the "Accept the offer" model (`notes/activitystreams-semantics.md`):
`Accept(object=<Invite>)` — the actor accepts the *proposal activity*, not the
thing being proposed. This parallels the fix applied to `RmAcceptInviteToCase`
and `RmRejectInviteToCase` in `vultron/as_vocab/activities/case.py` on
2026-02-20.

Fix both classes before implementing BT-5.2 handlers. Also update any
vocab examples (`vultron/scripts/vocab_examples.py`) and tests that assert on
the old structure.

### `VulnerabilityCase.set_embargo()` bug — RESOLVED

Confirmed fixed: `set_embargo()` now calls `self.current_status.em_state =
EM.ACTIVE` via the `current_status` property (sorted by `updated` timestamp).
The `BUGS.md` entry has been cleared. No action needed.

### Demo script gap

`vultron/scripts/invite_actor_demo.py` does not yet exist. This is the
BT-4.3 deliverable. It should:
1. Call `initialize_case_demo` setup functions as preconditions.
2. Demo: case owner invites a second actor → second actor accepts → participant
   added to case → show updated participant list.
3. Include a test in `test/scripts/` mirroring `test_initialize_case_demo.py`.

### AGENTS.md lazy imports guidance update needed

The current AGENTS.md advises using lazy imports (inside functions) to avoid
circular import issues. In practice, module-level imports are preferred for
readability and discoverability. The guidance should be updated to say:
*prefer module-level imports; use lazy imports only when a circular dependency
cannot be refactored away*. Local imports already present in the codebase are a
code smell indicating potential circular dependencies to be refactored over time.

This update is low priority but should be done before the next agent picks up
the codebase to avoid confusion.

---



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

### Deferred: embargo flow complexity and `ChoosePreferredEmbargo`

The embargo flow also involves `ChoosePreferredEmbargo` (a Question type),
making the semantics more nuanced. Deferring to BT-5 implementation.
`ChoosePreferredEmbargo` is known to be underspecified and may require 
additional details before it can be implemented. It should be treated as a lower
priority than the rest of the Embargo Management process. At any given time, 
the most likely scenario is that the case has zero or one active embargo, 
with zero or one pending embargo proposal. The `ChoosePreferredEmbargo` activity
would only come into play in the far less common scenario when there are 
multiple pending embargo proposals (e.g., from different actors) and the case 
participants need to resolve which one to accept. This is an extreme corner case
and may in fact be unnecessary to implement, because the "0/1 active, 0/1 
pending" scenario is likely to cover the vast majority of real-world cases.

---

### Prototype must conform to ActivityStreams Vocabulary spec

In cases like "Remove" where the ActivityStreams spec defines a specific 
structure (e.g., `Remove` Indicates that the `actor` is removing the 
`object`. If specified, the `origin` indicates the context from which the  
object is being removed.), the prototype implementation must conform to that 
structure. If current implementation is inconsistent with the ActivitStreams 
spec, it should be refactored to align with the spec. This is important for
ensuring that the implementation is interoperable with other systems that also
conform to the ActivityStreams spec.

---

### Object and activity IDs should be treated as strings

Even if we are generating UUIDs for ActivityStreams object and activity IDs 
using semantic structures, the implementation should treat these IDs as opaque 
strings. This is important for ensuring that ID generation can be site-specific
and flexible, and that the implementation can interoperate with other systems that
may have different ID generation strategies. The implementation should not make
assumptions about the structure of IDs. This will imply a need to encode strings
so that they are, for example, URL-safe if they are being used in contexts where certain characters
might cause issues. This is a common practice when using UUIDs or other complex strings as IDs.

---

### Handlers module is becoming unwieldy — consider refactor into submodules

The Handlers module is well over a thousand lines and growing as the prototype 
development continues. We should consider refactoring it into multiple 
submodules in a `vultron/api/v2/backend/handlers/` directory. Organizing the 
handlers by topic or business proces (e.g., case management, report 
management,  embargo management, etc.) could make the codebase more 
navigable  and maintainable as it grows. This is not an urgent priority while
we are still building out the initial demos, but it should be on the roadmap
for the next phase of development after the initial demos are complete.

---

### Vocab Examples script should be turned into a module with submodules

The vocab examples module in `vultron/scripts/vocab_examples.py` is 
actually a module that is used by other things, including the API demos and the
documentation build process. It would be better suited as a new module with 
submodules outside of the `vultron/scripts` directory. For example, it could 
be moved to `vultron/as_vocab/examples/` with submodules organized by topic.
It probably makes sense for the examples and handlers to share a common 
convention for organizing code by topic, so if we refactor the handlers into
submodules by topic, we should also refactor the vocab examples into submodules 
by the same or similar topics.

---

## CaseStatus is an append-only list that captures the history of status changes for a case

Code should not modify existing `CaseStatus` objects inside a case. Instead,
you should create a new `CaseStatus` object for each status change and append it to the
case's list of statuses. The current status of the case can be determined by
looking at the most recently added `CaseStatus` object in the list (e.g., by 
sorting by the `updated` timestamp). This approach allows us to maintain a 
complete history of status changes for each case, which can be important for 
auditing and understanding the lifecycle of a case. It also simplifies the logic 
for handling status changes, as we don't have to worry about modifying 
existing  objects or maintaining complex state transitions.

A helper method could be implemented on VulnerabilityCase to facilitate finding
the current status, e.g., a property that returns the most recent CaseStatus
based on the updated timestamp.

---

## Demo scripts belong in `vultron/demo/` not `vultron/scripts/`

The `vultron/scripts/*_demo.py` scripts are intended to be for demonstration
purposes, and so they are not really "scripts" in the traditional sense of 
being standalone utilities that can be run independently for some user 
facing purpose. They should be moved to the `vultron/demo/` directory to 
reflect their purpose as demos. This is not urgent, but it should be on the 
roadmap for the next phase of development after the initial demos are 
complete. Because these demos are also depended on by the test suite and docker
configs, the move will need to account for those dependencies and update 
import paths accordingly. The `vultron/scripts/` directory can be reserved for
actual utility scripts that are intended to be run independently by users, such
as data migration scripts, maintenance utilities, or other tools that are 
not specifically for demonstration purposes. Update documentation specs if
needed to reflect this distinction between `demo/` and `scripts/`.

---

## Embargo management process in a nutshell

There have been recent difficulties in implementing the embargo management 
process in part due to fact that the initial implementations didn't necessarily
align with how ActivityStreams models the semantics of Invite/Accept/Reject 
patterns. The core concept of embargo management is that it's essentially an 
analog to inviting actors to a meeting. You send out an invitation to a 
calendar event, and the invitees can accept or reject that invitation. The 
inviting party then reviews the individual responses and decides whether to 
propose a new schedule or go with the proposed one. Someone might reply "I 
can't make it Tuesday at noon, but could we do Wednesday at 3pm instead?" 
This is a counter proposal, an Invite InReplyTo the original Invite. There 
is guidance in the documentation that may be informative about the process 
as well. These should be reviewed and internalized into `specs/*` and `notes/*`
as needed to ensure that the implementation of the embargo management process is
aligned with the intended semantics and design.

- `docs/topics/process_models/em/principles.md`
- `docs/topics/process_models/em/defaults.md`
- `docs/topics/process_models/em/negotiating.md`
- `docs/topics/process_models/em/working_with_others.md`
- `docs/topics/process_models/em/early_termination.md`
- `docs/topics/process_models/em/split_merge.md`

---


