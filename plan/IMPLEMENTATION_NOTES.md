# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

### Engagement Semantics: Accept/Defer vs. Undo(Ignore)

Contrary to a prior implementation note, we
do **not** introduce a separate `ReEngage` or `Undo(Ignore)` activity.
Engagement is derived directly from the Report Management (RM) DFA state:
`Accepted` = engaged, `Deferred` = not actively engaged. Because the RM model
already permits reversible transitions between `Accepted` and `Deferred`,
re-engagement is simply an `accept` transition emitted from the `Deferred`
state. Introducing `Undo(Ignore)` would duplicate existing DFA semantics without
adding expressive power.

`Undo` in ActivityStreams implies retracting the effects of a prior action,
which is not the intended meaning here. Re-engagement is a forward state
transition, not a historical negation. Using only `accept` and `defer` preserves
a minimal symbol set, maintains clean audit histories, simplifies reasoning over
case histories, and keeps engagement distinct from participation semantics such
as `Leave` (which represents permanent departure rather than temporary
deferral).


---

## 2026-02-24 — Gap Analysis Notes (refresh #6)

### Missing MessageSemantics (BT-8)

Three activity types are in `vultron/as_vocab/` and referenced by vocab_examples
but have no `MessageSemantics` entry, no `ActivityPattern`, and no handler:

- **`RmReEngageCase`** (`as:Undo` of `RmDeferCase`) — used in `manage_case.md` and has a `reengage_case()` factory in `vocab_examples.py` that returns a raw `as_Undo`. A named `RmReEngageCase(as_Undo)` class does not yet exist in `vultron/as_vocab/activities/case.py`. Semantics: undo deferral → transition actor's `ParticipantStatus.rm_state` back to ACCEPTED.

See implementation note above for rational on why REENGAGE_CASE is not
needed as a separate semantic type.
Instead, this should imply that we need to update the documentation in  
`manage_case.md` to reflect that re-engagement is done via the existing  
`accept` activity, which transitions the actor's RM state back to ACCEPTED
from DEFERRED. The documentation should clarify that there is no separate  
REENGAGE_CASE activity, and that actors can simply use the accept action to  
re-engage with a case they had previously deferred.

2. **`UpdateCase`** (`as:Update(VulnerabilityCase)`) — class exists in
   `vultron/as_vocab/activities/case.py` but is not wired into the handler
   pipeline at all.

Note: This might be overly generic as a semantic type. Most of the things 
that happen to a case are specifically the subject of a more specific 
activity type that carries its own semantics (e.g., EngageCase, CloseCase, AddParticipant).
There may be a need for an `UpdateCase` activity to be able to capture other
updates to cases, though, so it's most likely useful to have it and the 
semantics in place, even if it's only rarely used for a CaseActor to emit an 
UpdateCase activity for otherwise uncaptured updates to a case.

4. **`ChoosePreferredEmbargo`** (`as:Question`) — class exists in
   `vultron/as_vocab/activities/embargo.py` but not wired in.

See `notes/activitystreams-semantics.md` for discussion of the likely lack 
of need for a separate semantic type for this activity. The 
`ChoosePreferredEmbargo` is an artifact of a prior design iteration where we 
were thinking about using `as:Question` as a polling mechanism if multiple 
embargo choices were on the table at once. However, as the notes indicate, 
this is a very edge case situation and so we should probably remove it from the 
design and documentation except to note that we could add it in the future if
it becomes relevant to do so. It's okay for the placeholder to remain in 
`embargo.py` but not really worth wiring it into a handler because of the 
complexity that it would add to the workflow for a situation that is 
expected to be rare and for which we already have a viable workaround in just
sequentialy emitting multiple `OfferEmbargo` activities that can be accepted 
or rejected independently if there are multiple embargo options to choose from.

All three must be added before `manage_case_demo.py` and
`manage_embargo_demo.py`
can cover their full documented workflows.

### CM-03-006 Rename Risk

`VulnerabilityCase.case_status` (list field with singular name) is referenced
throughout `handlers.py` (~20 call sites), `behaviors/`, and many tests.
The rename to `case_statuses` is a correctness improvement per the spec but
carries significant breakage risk. Run `grep -rn "\.case_status" vultron/ test/`
before starting to quantify scope. Consider doing `case_statuses` and
`participant_statuses` renames in the same PR to keep the diff localized.

### Outbox Delivery Gap

`vultron/api/v2/data/actor_io.py` has a placeholder that appends strings to an
outbox list but does not write to any recipient actor's inbox. No delivery
mechanism exists. This means outbox-based activities (e.g., CreateCase
activity generated by `create_case` handler) are never actually received by
other actors. This is acceptable for the prototype demos (which sequence
activities manually) but must be resolved before the `CaseActor` broadcast
model (Priority 200) can work correctly.

### Demo Script Gap Summary

Per `plan/PRIORITIES.md`, the following howto workflows still need demo scripts:

- **Higher priority**: `acknowledge.md`, `manage_case.md`,
  `initialize_participant.md`, `manage_embargo.md`, `manage_participants.md`
- **Lower priority**: `error.md`

Note: `manage_case_demo.py` depends on BT-8 (REENGAGE_CASE handler) for a
complete workflow. The demo can be written without it by skipping the reengage
step, but adding REENGAGE_CASE first is cleaner.
