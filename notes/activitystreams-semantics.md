---
title: ActivityStreams Semantics in Vultron
status: active
description: >
  Activities as state-change statements, not commands; inbound/outbound
  semantics, Accept/Reject object rules, and rehydration.
related_specs:
  - specs/semantic-extraction.yaml
  - specs/response-format.yaml
  - specs/case-management.yaml
related_notes:
  - notes/bt-integration.md
relevant_packages:
  - pydantic
  - vultron/wire/as2
  - vultron/core/models/events
---

# ActivityStreams Semantics in Vultron

## Activities Are State-Change Notifications, Not Commands

In Vultron, an ActivityStreams Activity is a **statement about a state change
that has already occurred**, not a request for another Actor to perform an
action.

When an Actor receives an Activity, it is being informed that:

- Another Actor performed a state transition in their RM, EM, or CS process.
- The shared state of the Case has changed.
- The sender's internal model of the world has been updated accordingly.

The receiver MUST treat the Activity as an assertion about the sender's state
and update its own model of the world. This includes:

- The Case
- Reports
- Participants
- Embargo status
- Case state events (V, F, D, P, X, A)
- Known prior transitions

Receiving an Activity means:

> "Someone else observed or performed a state change and is informing me."

It does **not** mean:

> "I am being instructed to perform this action."

### Emitting Activities

When an Actor emits an Activity, it is declaring:

- "My internal state has changed."
- "I have performed a protocol-relevant transition."
- "The shared case state should now reflect this."

Activities are therefore:

- Distributed state synchronization signals.
- Logs of completed transitions.
- Assertions about protocol-visible facts.

They are **not**:

- Remote Procedure Calls.
- Commands.
- Requests to execute behavior.

### Work Outside the Protocol

Participants perform substantial work outside the Vultron messaging layer,
such as:

- Reproducing a vulnerability
- Root cause analysis
- Fix development
- Patch deployment
- Human embargo negotiation
- Document preparation

When such work results in a protocol-relevant state transition (e.g., Fix
Ready, Fix Deployed, Embargo Accepted), the Actor emits the corresponding
Activity.

**The Activity does not cause the work. The work causes the Activity.**

### Processing Is Still Required

Although Activities are not commands, recipients MUST still process them:

1. Parse and validate the Activity.
2. Update local RM/EM/CS state.
3. Potentially trigger local behaviors (e.g., reprioritize, start validation,
   update embargo tracking).

The key distinction is:

- Activities describe what has happened.
- Behavior logic determines what to do next in response.

---

## Response Activity Conventions

### inReplyTo

Responses to activities that imply a reply (Offer, Invite) MUST use the
`inReplyTo` field to reference the original activity. This is required for
threading and context.

For example, when responding to an Offer of a VulnerabilityReport:

- The response activity's `object` field MUST be the Offer/Invite being
  responded to.
- The response activity MUST set `inReplyTo` to the ID of the Offer/Invite.

This allows other actors to understand the relationship between the response
and the original offer.

**References**: `specs/response-format.yaml` RF-02-003, RF-03-003, RF-04-003,
RF-08-001.

---

## Vocabulary Examples as Canonical Reference

The directory `vultron/wire/as2/vocab/examples/` contains canonical examples
of every Vultron ActivityStreams activity type, split into submodules by
topic: `actor.py`, `case.py`, `embargo.py`, `note.py`, `participant.py`,
`report.py`, `status.py`. These examples serve as:

- **Documentation**: Illustrate the expected structure for each message type.
- **Pattern-matching reference**: Show which `(Activity Type, Object Type)`
  pairs correspond to each `MessageSemantics` enum value.
- **Test fixtures**: Provide well-formed activity structures for unit tests
  against `vultron/wire/as2/extractor.py` and handlers.

When implementing or testing a new handler, consult the examples submodules
first to understand the expected activity structure before looking at the
pattern definitions in `vultron/wire/as2/extractor.py`.

The examples MUST be kept up to date as the vocabulary evolves. When adding a
new vocabulary type or message semantic, add a corresponding example to the
appropriate submodule in `vultron/wire/as2/vocab/examples/`.

**Cross-references**: `vultron/wire/as2/extractor.py`,
`vultron/core/models/events.py`, `vultron/wire/as2/vocab/`.

---

## Asymmetric Inbox Routing for Invite/Accept/Reject

Invite, Accept, and Reject activities are **not** all received by the same
actor. Each activity hits the inbox of a **different** actor:

| Activity | Sender | Recipient inbox | Handler |
|----------|--------|-----------------|---------|
| `Invite(object=Actor, target=Case)` | Case Owner | Target Actor | `invite_actor_to_case` — stores invite for local consideration |
| `Accept(object=Invite)` | Target Actor | Case Owner | `accept_invite_actor_to_case` — creates `CaseParticipant` |
| `Reject(object=Invite)` | Target Actor | Case Owner | `reject_invite_actor_to_case` — logs rejection |

**Consequence for implementation**: The `CaseParticipant` creation logic
belongs in `accept_invite_actor_to_case` (the case owner's inbox handler),
**not** in `invite_actor_to_case` (the target actor's inbox handler). Each
actor only processes their own inbox.

This asymmetry is easy to miss. It reflects the ActivityPub convention that
responses are addressed to the original sender, and the work triggered by the
response (creating a participant record) is the responsibility of the party
who initiated the flow (the case owner).

The same pattern applies to embargo Invite/Accept/Reject flows:
`invite_to_embargo_on_case` hits the invitee's inbox, while
`accept_invite_to_embargo_on_case` hits the inviter's (case owner's) inbox.

**Reference**: `docs/howto/activitypub/activities/invite_actor.md`,
`docs/howto/activitypub/activities/establish_embargo.md`.

---

## Rehydration Before Pattern Matching

ActivityStreams allows both inline objects and URI string references in
activity fields. Before performing semantic pattern matching, activities MUST
be rehydrated to expand string URI references into full objects.

The `inbox_handler.py` performs rehydration before dispatching, so handlers
receive fully expanded objects. However, when calling `find_matching_semantics`
outside of the dispatch pipeline, call `rehydrate()` explicitly:

```python
from vultron.wire.as2.rehydration import rehydrate

activity = rehydrate(activity)
semantic = find_matching_semantics(activity)
```

**References**: `specs/semantic-extraction.yaml` SE-01-002,
`vultron/wire/as2/rehydration.py`.

---

## Embargo Management as Calendar Invitation

The embargo management flow is structurally analogous to inviting actors to
a calendar event:

1. A **proposer** sends an `Invite(object=Actor, target=EmbargoEvent)` to
   each participant — "can you make this time slot?"
2. Each invitee **accepts** or **rejects**: `Accept(object=Invite)` /
   `Reject(object=Invite)` — "yes I can" / "no I can't."
3. A participant may **counter-propose** a different embargo window by sending
   a new `Invite` with `inReplyTo` referencing the original — "I can't do
   Tuesday noon, can we do Wednesday at 3pm?"
4. Once all relevant parties accept, the embargo becomes `ACTIVE`.

Key consequence: `Accept(object=<Invite>)` — the actor accepts the
**proposal activity** (the `Invite`), not the `EmbargoEvent` being proposed.
This is the same pattern as `RmAcceptInviteToCase`. The `as_object` field on
`EmAcceptEmbargo` must reference the `EmProposeEmbargoRef` (the Invite), not
the `EmbargoEventRef`.

**Reference docs**: `docs/topics/process_models/em/` (principles, defaults,
negotiating, working_with_others, early_termination, split_merge).

---

## ChoosePreferredEmbargo Is a Corner Case

`ChoosePreferredEmbargo` (a Question type) is only relevant when **multiple
simultaneous embargo proposals** exist from different actors. In practice,
most cases will have at most one active proposal at a time (0 or 1 active
embargo, 0 or 1 pending proposal). The `ChoosePreferredEmbargo` activity
is therefore a low-priority edge case; implement it only after the core
propose/accept/reject flow is fully working and tested.

---

## `VulnerabilityCase.case_activity` Cannot Store Typed Activities

`VulnerabilityCase.case_activity: list[as_Activity]` uses
`as_Activity.as_type: as_ObjectType`. The `as_ObjectType` enum covers only
core AS2 object types (`'Activity'`, `'Note'`, `'Event'`, etc.) — it does
**not** include transitive activity types like `'Announce'`, `'Add'`,
`'Accept'`, `'Reject'`, etc.

**Consequence**: Writing a typed activity (e.g., `AnnounceEmbargo`) to
`case_activity`, serializing, and reloading causes `model_validate` to fail
with `Input should be 'Activity', 'Actor', ...`. The `record_to_object`
fallback returns a raw `TinyDB Document`, losing all typed state silently.

**Fix pattern**: Handlers that would add specific-typed activities to
`case_activity` MUST log the event instead. Only use `case_activity` for
generic `as_Activity` objects if the activity type is guaranteed to be a
core AS2 type.

**Reference**: `notes/bt-integration.md` (BT integration design decisions).

---

## Accept/Reject `object` Field MUST Use an Inline Typed Activity Object

When constructing `Accept`, `Reject`, or `TentativeReject` responses to an
`Invite` or `Offer`, set the `object_` field to the **full typed inline
activity object** — not a bare string ID. Bare string IDs are rejected by
Pydantic validation at construction time (enforced by INLINE-OBJ-B).

**Pattern**:

```python
# Correct: object_ is the full typed inline activity object
accept = RmAcceptInviteToCase(
    actor=responding_actor.id_,
    object_=invite,  # RmInviteToCaseActivity instance
)

# Incorrect: bare string ID raises pydantic.ValidationError
accept = RmAcceptInviteToCase(
    actor=responding_actor.id_,
    object_=invite.id_,  # ValidationError at construction time
)
```

### Reading from the DataLayer

The DataLayer adapter dehydrates nested `object_` fields to ID strings on
write. When reading an Accept/Reject activity back from the DataLayer, the
stored offer or invite must be re-read separately and coerced before
constructing the response:

```python
# Read the stored offer/invite from the DataLayer
raw = dl.read(offer_id)
# Coerce to the correct typed subclass
invite = RmInviteToCaseActivity.model_validate(raw.model_dump(by_alias=True))
# Now pass as object_ to the response activity
accept = RmAcceptInviteToCase(actor=actor.id_, object_=invite)
```

> **Note**: Once `DL-REHYDRATE` is implemented (`plan/IMPLEMENTATION_PLAN.md`),
> `dl.read()` will return fully rehydrated typed objects automatically and the
> manual `model_validate` coercion step above will no longer be needed.

This applies to all `Accept`/`Reject`/`TentativeReject` responses to
`Invite`/`Offer` activities.

**Cross-reference**: `specs/response-format.yaml` RF-02-003, RF-03-003,
RF-04-003, RF-08-001; `specs/datalayer.yaml` DL-01-001.

---

## Re-Engagement Uses `RmEngageCase`, Not a Separate Activity

Re-engaging a deferred case does **not** use a separate `RmReEngageCase`
activity. Instead, the existing `RmEngageCase` (`as:Join`) activity is
reused for re-engagement.

**Rationale**: The RM model already permits reversible transitions between
`ACCEPTED` and `DEFERRED`. Re-engagement is a forward state transition —
the actor in `DEFERRED` emits an `accept` transition to move back to
`ACCEPTED`. Introducing `Undo(Ignore)` was considered and rejected:

- `as:Undo` implies retracting the *effects* of a prior action (historical
  negation), not a new forward transition.
- Using only `RmEngageCase` and `RmDeferCase` preserves a minimal symbol set,
  produces clean audit histories, and keeps engagement distinct from
  participation semantics such as `RmCloseCase` (`as:Leave`), which
  represents permanent departure rather than temporary deferral.

**Consequence for implementation**: The `reengage_case()` factory in
`vultron/wire/as2/vocab/examples/case.py` returns a raw `as_Undo` — this is a
legacy artifact for documentation purposes only. Actual re-engagement MUST
be implemented as a second `RmEngageCase` (`as:Join`) activity.

**Reference**: `docs/howto/activitypub/activities/manage_case.md` ("Re-Engaging
a Case" note), `vultron/demo/manage_case_demo.py` (`demo_defer_reengage_path`).

---

## Case State Update Path and CaseActor Authoritativeness

Each actor MAY maintain a local copy of a `VulnerabilityCase` object for
performance or offline use. However, the **CaseActor is the authoritative
source of truth** for all case state updates. Local copies MUST be treated
as cached projections, not independent sources of truth.

The canonical update path when an actor modifies case-related state is:

```text
Actor → CaseActor inbox
  → CaseActor updates canonical case state
  → CaseActor broadcasts update to all CaseParticipants
  → Each participant updates its local copy
```

**Consequence**: Actors MUST NOT directly accept case state updates from
other regular actors. Updates received from any source other than the
CaseActor MUST be ignored (or at minimum flagged for verification). This
ensures the CaseActor remains the single coordination point and prevents
conflicting state divergence.

**Authentication note** (`PROD_ONLY`): In production, participants MUST
authenticate that a case update originated from the CaseActor before
treating it as authoritative (see `specs/case-management.yaml` CM-06-002,
CM-06-004).

**Current status**: The CaseActor broadcast is implemented in
`vultron/core/use_cases/received/case.py` (`UpdateCaseReceivedUseCase`)
via `_broadcast_case_update()`, which fans out updates to all case
participants (see `specs/case-management.yaml` CM-06-001, CM-06-002;
completed in PRIORITY-200 CA-2, 2026-03-25).

**Cross-reference**: `specs/case-management.yaml` CM-02-002, CM-06.

---

### Activity `name` Field: Use Semantic Content, Not Repr

(DR-02, 2026-04-20)

The `name` field of outbound activities is **semantic content** — a
human-readable label — not a wire-format concern. BT nodes that construct
outbound activities with a `name` field MUST derive it from the object's own
attributes:

```python
# Correct
activity_name = object_.name or object_.id_

# Wrong — never use repr() or str()
activity_name = repr(object_)
activity_name = str(object_)
```

The outbound adapter (`outbox_handler.py`) does not sanitize semantic content.
Audit any BT node in `vultron/core/behaviors/` that constructs `Add`, `Invite`,
or `Accept` activities with a computed `name` string.

---

### `cc` Addressing Is Not Supported

(DR-13, 2026-04-20)

`cc` addressing has no defined handler semantics in the current protocol
version. When a receiving actor is in `cc` of an `Offer(Report)` activity:

- Log **WARNING** (not DEBUG): "`cc` addressing is not supported; activity
  discarded"
- Discard the activity without creating a case

This is a deliberate simplification. Implementing an "informational receive"
use case for `cc` recipients would require defining what "informational only"
means, which is deferred.

See `specs/handler-protocol.yaml` for the `to`-only case-creation rule.

---

### Dead-Letter Handling for Unresolvable `object_` References

(DR-14, 2026-04-20)

When `find_matching_semantics()` returns `UNKNOWN` because `object_` is still
a bare string URI after rehydration, this is a **different failure mode** from
UNKNOWN due to no registered pattern. The two cases require different handling:

| Failure mode | Cause | Handler |
|---|---|---|
| `UNKNOWN_NO_PATTERN` | No matching `ActivityPattern` | Raise `VultronApiHandlerMissingSemanticError` |
| `UNKNOWN_UNRESOLVABLE_OBJECT` | `object_` still bare string after rehydration | Log WARNING, store dead-letter record, return silently |

Dead-letter record schema:

```json
{
  "activity_id": "urn:uuid:...",
  "activity_json": {},
  "unresolvable_uri": "https://...",
  "actor_id": "https://...",
  "received_at": "2026-..."
}
```

For future synchronous paths: return HTTP 422 Unprocessable Content with the
unresolvable URI in the error body.

See `specs/semantic-extraction.yaml` VAM-01-009.

---

### Accept.object_ Must Carry the Invite Activity, Not the Case Object

(DR-05, 2026-04-20)

When constructing an `Accept(Invite(...))` activity, the `object_` field MUST
be the original `Invite` activity (retrieved from the BT blackboard), not the
case or embargo event.

**Wrong pattern** — passing the case or embargo event as `object_`:

```python
# This produces coercion failures on the receiving end
accept = RmAcceptInviteToCaseActivity(
    actor=actor_id,
    object_=case,          # ← WRONG: must be the Invite activity
)
```

**Correct pattern** — stash invite on blackboard; read it back in Accept node:

```python
# In InviteReceivedUseCase.execute() — store invite on blackboard
bb.set("invite_activity", invite)

# In AcceptInviteNode.update() — read invite from blackboard
invite = bb.get("invite_activity")
accept = RmAcceptInviteToCaseActivity(actor=actor_id, object_=invite)
```

This ensures that `Accept` activities satisfy the AS2 convention: the
`object` of an `Accept` is the activity being accepted.

---

### Open Question: Actor Subtype-Aware Pattern Matching

(DR-07 Update, 2026-04-20)

`InviteActorToCasePattern` in `vultron/wire/as2/extractor.py` has no
`object_` field, violating SE-03-003. The correct structure per AS2 is
`Invite(object=Actor, target=Case)`.

**Constraint discovered (2026-04-20)**: `AOtype.ACTOR = "Actor"` only matches
the base `as_Actor` class (`type_="Actor"`). Real AS2 actor subtypes
(`VultronPerson`, `VultronOrganization`, `CaseActor`) have `type_="Person"`,
`type_="Organization"`, `type_="Service"` respectively. The pattern matcher
uses exact string equality, so `object_=AOtype.ACTOR` would NOT match real
invite objects containing actor subtypes. Adding it breaks existing tests and
real invite flows.

**Required fix before this can be implemented**: Add subtype-aware matching
in `_match_field()` (e.g., check `isinstance(activity_field, as_Actor)`) or
a custom actor-type predicate in `ActivityPattern`.

**Open Question**: What is the right predicate API for ActivityPattern
subtype matching? Options include:

1. `object_type_predicate = lambda obj: isinstance(obj, as_Actor)` — flexible
   but non-declarative
2. A `subtype_of` field on `ActivityPattern` that maps to a class — consistent
   with the existing `object_type` string field

Until subtype-aware matching is implemented, `InviteActorToCasePattern`
should remain without an `object_` constraint and this open question tracked
in the pattern audit.

---

### Transitive Activity `object_` Field: Contract at the Base Type

(BUG-26041802, 2026-04-22)

If a field is semantically required across an entire AS2 activity family, the
**shared base type** must encode that requirement. Keeping
`as_TransitiveActivity.object_` optional lets generic constructors drift out
of sync with the stricter typed subclasses.

**Key lessons:**

- Use a **distinct required-reference alias** (`ActivityStreamRequiredRef`)
  rather than just changing a `Field(...)` default. `ActivityStreamRef` still
  includes `None`, so type-level and runtime contracts diverge unless required
  fields use the stricter alias.
- Wire/domain translation tests must reflect the stricter contract too:
  `VultronAS2Activity.from_core()` should reject objectless transitive domain
  activities rather than silently materializing invalid wire objects.
- A backlog bug may already be fixed; close it with concrete code-search and
  regression-test evidence (see also `notes/bugfix-workflow.md`).

---

### Base-Typed Activity Serialization Can Drop Inline Subtype Fields

(BUG-26042201, 2026-04-22)

When a typed AS2 activity stores `object_` through a base reference annotation
(`as_ObjectRequiredRef`), plain `model_dump()` can serialize the nested value
as the base `as_Object` shape and silently omit subtype-only fields.

**Fix**: For any adapter path that re-validates or delivers rehydrated
activities, prefer `model_dump(..., serialize_as_any=True)` so inline typed
payloads (such as `CaseLogEntry`) survive semantic coercion and HTTP delivery
intact.

**Regression coverage** MUST hit **both** the persistence boundary AND the
outbound delivery boundary. A DataLayer round-trip test alone will NOT catch
the same field loss in the outbox adapter.

---

### Invite Response Parsing: Recursive Rehydration and Stub Expansion

(BUG-26042203, 2026-04-22)

**Lesson 1 — Generic AS2 parsing must recurse into nested inline dicts.**

`Accept(Invite(...))` and `Reject(Invite(...))` contain an `Invite` as their
`object_`. If the parser only recurses into the outer `object` field and not
into fields of the nested dict, the `Invite`'s own `actor` and `object_`
(typically a case stub) are left as raw dicts, breaking `ActivityPattern`
matching that relies on typed subtype information.

**Lesson 2 — Minimal case dicts must expand to `VulnerabilityCaseStub`.**

Minimal `{"id": "...", "type": "VulnerabilityCase"}` dicts received in
inbound activities (e.g., as the `object_` of an `Invite`) should be expanded
as `VulnerabilityCaseStub`, not full `VulnerabilityCase`. This preserves
selective-disclosure semantics: the invitee has not yet accepted the embargo,
so they should only see the stub. Expanding to full `VulnerabilityCase` would
incorrectly materialize fields the invitee has not yet earned access to.

**Lesson 3 — `inReplyTo` belongs on the model, not only on call sites.**

Setting `inReplyTo` directly on invite accept/reject activity models (as a
constructor parameter with a default that reads the invite ID) is a safer
invariant than relying on every trigger/demo/example call site to wire the
original invite ID correctly. Model-level defaults prevent accidental omission.
