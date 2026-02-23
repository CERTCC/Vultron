# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate 
insights, issues, and learnings during the implementation process.

Add new items below this line


---

## Bug Fixed: CreateParticipant activity "name" attribute (2026-02-23)

Overrode `set_name()` in `CreateParticipant`
(`vultron/as_vocab/activities/case_participant.py`) to produce a descriptive name:
`"{actor} Create CaseParticipant {participant_id} from {attributed_to} in {case_id}"`.

Root cause: the default `as_TransitiveActivity.set_name()` used `name_of(as_object)`
which for a `CaseParticipant` returns the participant's `name` field — which is set
to `attributed_to` (an actor URI) by `CaseParticipant.set_name_if_empty`. The result
was `"{actor_uri} Create {actor_uri}"`, making it look like actor creation.

Fix: override `set_name` in `CreateParticipant` using `as_object.as_id` (the
participant ID) and `as_object.attributed_to` (the underlying actor), plus the
`context` field for case correlation.

---

## Object IDs are causing problems as they are handled inconsistently

ActivityStreams Object IDs should be handled consistently as strings across the codebase.
Previous implementations tried to shortcut by only using bare UUIDs instead of 
full URIs, but this has caused confusion and bugs because some parts of the code
write the full URI while others write just the UUID, and some parts expect one 
format while others expect the other. This inconsistency has led to bugs where 
an ID is stored as a full URI but then later accessed as if it were a bare UUID,
causing erroneous reports of missing data or incorrect behavior. To fix this,
we should standardize on using full URIs for all Object IDs in the codebase, 
and ensure that all code that reads or writes Object IDs is updated to use this 
format consistently. See in particular the datalayer where sometimes UUIDs are
appended to URLs, and anywhere that Object IDs are being parsed as if they have
internal structure (hint: we should not assume Object IDs have any internal 
structure at all, they should be treated as opaque URI strings properly 
URL-encoded).

---

## `case_status` and `participant_status` field names are misleading and should be pluralized

`VulnerabilityCase.case_status` is misnamed. It is actually a list of 
`CaseStatus` objects. It should be renamed to `case_statuses` to reflect that it
is intended to hold multiple status objects over the lifecycle of the case.
This is important for debugging as it has confused me multiple times when I 
forget that `case_status` is a list and I try to access it as if it were a 
single object. The same applies to `CaseParticipant.participant_status`, which 
should be renamed to `participant_statuses` for the same reason.
This would allow for the singular `case_status` and `participant_status` to be
used as a property that could return the current status of the case and 
participant (by date), respectively, without having to access the list and find
the most recent status. This would make it easier to access the current status 
of the case and participant, while the plural versions can hold the history 
of status changes over time. The property should be implemented such that it is
read-only and does not permit setting the current status directly, as the status
should only be changed through the appending of a new status object to the list.

---

## Refactoring Large Modules is Important

The refactoring of `handlers.py` and `vocab_examples.py` is becoming more
urgent as we continue to implement more and more tasks that require modifying
these modules. See `notes/codebase-structure.md` for roadmap details.

---

## `as_` prefix for field names is only for reserved python keywords

The reason fields are `actor` and not `as_actor` is that we only use the 
`as_` prefix for field names that would otherwise conflict with python keywords
(e.g., `object` is a reserved keyword in Python, so we use `as_object` for the field name).

---

## Pattern matching for message semantics may need improvement to handle subclasses of as_Actor

Pattern matching for message semantics seems to break down when the pattern 
needs to match on a subclass of as_Actor, which will be any time it matches 
on as_Actor because as_Actor is the base class for all actors but any given
message will come from a specific subclass of as_Actor (e.g., as_Person, 
as_Organization, etc.). This is because the pattern matching may be overly 
simplistic and it needs to be smarter about matching on as_Actor subclasses.
Design a solution for this issue, which may involve implementing a more 
sophisticated pattern matching system that can recognize and match on subclasses
of as_Actor.

---

## BT-6: Notes and Status Handler Pre-Implementation Notes (2026-02-23)

Phase BT-6 implements the `status_updates` and `acknowledge` workflows
(`docs/howto/activitypub/activities/status_updates.md` and `acknowledge.md`).
All 7 handlers are currently stubs. Use procedural code (no BT needed — simple
CRUD with 1–2 steps per handler, no branching).

### Key Model Notes

- **`as_Note`**: Defined in `vultron/as_vocab/base/objects/object_types.py`.
  Use `as_NoteRef` for references. `AddNoteToCase` activity already defined in
  `vultron/as_vocab/activities/case.py`.
- **`CaseStatus`** / **`ParticipantStatus`**: Both defined in
  `vultron/as_vocab/objects/case_status.py`. `VulnerabilityCase.case_status` is a
  `list[CaseStatusRef]`. `CaseParticipant.participant_status` is a
  `list[ParticipantStatus]`.
- **`VulnerabilityCase` has no `notes` field**: The `AddNoteToCase` activity
  references a Note and a target Case, but `VulnerabilityCase` has no `notes`
  list. Two options: (a) add a `notes: list[as_NoteRef]` field to
  `VulnerabilityCase`, or (b) store notes only in DataLayer (note is persisted
  separately; no link from case to note). Option (a) is cleaner and consistent
  with how `case_participants` and `vulnerability_reports` are tracked.
  **Recommended: add `notes` field to `VulnerabilityCase`.**
- **`create_case_status`**: Creates a new `CaseStatus` and persists it. The
  case status tracks RM/EM/CS/VFD state. Handler should persist the new status
  object. The `add_case_status_to_case` handler then appends it to
  `case.case_status`.
- **Vocab examples**: `vocab_examples.py` already has `create_note()`,
  `add_note_to_case()`, `create_case_status()`, `add_status_to_case()`,
  `create_participant_status()` — use these as reference for handler inputs.

### BT-6.3: `ack_report` Review

`ack_report` already implements `RmReadReport`. The `acknowledge.md` doc
confirms `as:Read` is the correct activity type. Review against the doc
is a light verification task, not a reimplementation.

---

Previous agents are reporting that the IMPLEMENTATION_PLAN.md is too large 
to read at once. Is there a way to break it into smaller pieces? For example,
keep the IMPLEMENTATION_PLAN.md as a forward-looking plan and move the detailed
prior tasks and their status to a separate file that can be archived as needed?
E.g., "IMPLEMENTATION_LOG.md" or "IMPLEMENTATION_HISTORY.md" that would 
become an append-only file? Document choices into specs/project-documentation.md
and AGENTS.md files as appropriate.

---


## Case creation: vendor must be first participant; `attributed_to` = case owner

**Fixed (2026-02-23):** `initialize_case_demo.py` now adds a `VendorParticipant`
for the vendor (case creator) immediately after `CreateCase`, before the finder
participant. Steps renumbered 4a/4b (vendor participant) then 5/6/7 (report +
finder participant).

**`attributed_to` is the correct case owner field.** `VulnerabilityCase` is
created with `attributed_to=vendor.as_id`. The `accept_case_ownership_transfer`
handler also updates `attributed_to` when ownership changes. No model change
needed.

**Test fix:** The pre-existing `test_initialize_case_demo` test was silently
running 0 demos in the full suite due to a stale function reference after
`importlib.reload()` in `test_invite_actor_demo`'s teardown. Changed to call
`demo.main(skip_health_check=True)` (no `demos=` filter) so it always runs all
demos in the module, removing the function-identity dependency.

---


### BT-7: Suggest Actor + Ownership Transfer Handlers

**Accept/Reject always wraps the Offer, not the thing being offered.**
This applies uniformly across the protocol:

- `AcceptActorRecommendation.as_object` → `RecommendActor` (the Offer)
- `RejectActorRecommendation.as_object` → `RecommendActor` (the Offer)
- `AcceptCaseOwnershipTransfer.as_object` → `OfferCaseOwnershipTransfer` (the Offer)
- `RejectCaseOwnershipTransfer.as_object` → `OfferCaseOwnershipTransfer` (the Offer)

This is consistent with all other Accept/Reject pairs (e.g., `EmAcceptEmbargo`
wraps `EmProposeEmbargo`, `RmAcceptInviteToCase` wraps `RmInviteToCase`).

**`AcceptActorRecommendation` model was incorrect**: Previously used
`as_ActorRef` as the `as_object` type. Fixed to `RecommendActor | str | None`.

**`match_field` bug**: When `activity_field` is a string (URI ref) and
`pattern_field` is an `ActivityPattern`, the old code called
`pattern_field.match(str)` which crashed with `AttributeError`. Fix: check
`isinstance(activity_field, str)` before the `ActivityPattern` branch and
return `True` conservatively.

**`accept_case_ownership_transfer`**: Rehydrates the stored Offer to get the
case ID, then reads the case from the data layer. TinyDB returns a `Document`
with structure `{id_, type_, data_: {...}}`; read `record["data_"]["attributed_to"]`
directly (not via `record_to_object()`).

---

## Bug: `add_case_status_to_case` must append full object, not bare ID string

**Root cause (2026-02-23):** `add_case_status_to_case` was appending `status_id`
(a plain UUID string) to `case.case_status` instead of the full `status` object.
`VulnerabilityCase` has a `@model_validator(mode="after")` called `set_cs_context`
that iterates `case_status` and sets `cs.context = self.as_id` on every item. When
a bare string is present in that list, the validator crashes with:

    AttributeError: 'str' object has no attribute 'context'

This exception was silently swallowed by the `except` block, so `dl.update()` was
never called and the case was never persisted with the new status. The fix is to
append the rehydrated `status` object rather than `status_id`.

**Note:** `add_note_to_case` appends a bare string ID to `case.notes` and works
because `VulnerabilityCase` has no equivalent model validator over `notes`. The two
fields behave differently; `case_status` requires full objects.

**Tests added:** `test/scripts/test_status_updates_demo.py`,
`test/scripts/test_suggest_actor_demo.py`,
`test/scripts/test_transfer_ownership_demo.py` — 6 new parametrized tests covering
the three previously-untested demo scripts. The `status_workflow` test is a
regression test for the bug above.
