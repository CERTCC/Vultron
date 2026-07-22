---
title: "ActivityStreams: Case State Update and Advanced Patterns"
status: active
description: >
  Case state update path, CaseActor authoritativeness, DR-series named bugs,
  transitive activity patterns, base-typed serialization, invite response parsing,
  bootstrap embedded-object contract, semantic registry patterns, and
  offer_case_participant_activity object-id semantics.
related_specs:
  - specs/semantic-extraction.yaml
  - specs/response-format.yaml
  - specs/case-management.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/bt-integration.md
relevant_packages:
  - pydantic
  - vultron/wire/as2
  - vultron/core/models/events
---

# ActivityStreams: Case State Update and Advanced Patterns

> See also: [activitystreams-semantics.md](activitystreams-semantics.md) for the first half of these design notes.

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

The CaseActor broadcast is implemented in
`vultron/core/use_cases/received/case.py` (`UpdateCaseReceivedUseCase`)
via `_broadcast_case_update()`, which fans out updates to all case
participants (see `specs/case-management.yaml` CM-06-001, CM-06-002).

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
payloads (such as `CaseLedgerEntry`) survive semantic coercion and HTTP delivery
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

---

## Bootstrap Embedded-Object vs. URI-String Contract

(BUG-26051902, 2026-05-19)

All nested domain objects in a `Create(VulnerabilityCase)` bootstrap
activity (e.g., `CaseParticipant` records in `case_participants`) MUST be
included as **full inline objects**, not as bare URI string references.

**Why bare strings fail:**

Receiving use-case handlers store nested objects by iterating the embedded
collection and persisting each object individually to the local DataLayer.
`ActivityStreamRef` allows bare URI strings, so Pydantic accepts the field
without error — but the handler only persists non-`str` entries (materialized
objects). A bare URI string (e.g., `"urn:uuid:786aaff1-..."`) is silently
skipped; the referenced `CaseParticipant` is never written to the receiver's
DataLayer.

**Cascading failure mode (bug #561/#562):**

```text
1. Vendor sends Create(VulnerabilityCase) with case_participants as URI strings.
2. Finder's create_case_received handler iterates case.case_participants —
   strings are accepted by the model but skipped during persistence.
3. Vendor's CaseParticipant object is never stored in Finder's DataLayer.
4. Vendor sends RmEngageCase (Join) to Finder.
5. EngageCaseBT on Finder runs → CheckParticipantExists fails (no record).
6. RM-state update is never recorded in Finder's case replica.
```

**Fix**: When constructing the bootstrap case snapshot, serialize the
`VulnerabilityCase` with `model_dump(..., serialize_as_any=True)` to ensure
subtype fields (e.g., all `CaseParticipant` fields, not just base-type fields)
are retained. See also "Base-Typed Activity Serialization Can Drop Inline
Subtype Fields" in this file.

**Formal requirement**: `specs/case-bootstrap-trust.yaml` CBT-01-007.

---

## Semantic Registry Patterns Must Match Inbound Wire Format

(ISSUE-1298, 2026-07-10)

A semantic registry pattern maps an incoming AS2 activity shape to a
`MessageSemantics` value. The pattern MUST match the **inbound** wire format
— the shape that arrives in an actor's inbox from a peer — NOT the outbound
format that this actor emits.

`OFFER_ACTOR_TO_CASE` was initially mapped to `OfferActorToCasePattern`
(`Offer(CaseParticipant, Case)`) — the format that CaseActor sends to Case
Owner — instead of `SuggestActorToCasePattern` (`Offer(Actor, Case)`) — the
format that Finder sends to CaseActor's inbox.

`OfferActorToCasePattern` is still needed in `_instances.py` as a nested
template for `AcceptActorRecommendationPattern` and
`RejectActorRecommendationPattern` (which wrap `Offer(CaseParticipant)`).
Keep it in `_instances.py` but do NOT register it as a top-level registry
entry for `OFFER_ACTOR_TO_CASE`.

**Rule**: when adding a new registry entry, trace the message flow and
ask "who sends this, and what does the recipient's inbox receive?" The
registry matches the *receiver*'s perspective.

---

## `offer_case_participant_activity`: `event.object_id` Has `#participant` Suffix

(ISSUE-1298, 2026-07-10)

`offer_case_participant_activity(recommended, ...)` builds a `CaseParticipant`
with `id_=f"{recommended.id_}#participant"`. When extracted via
`extract_event()`, the event's `object_id` is the `CaseParticipant` URI
(e.g., `https://example.org/actors/vendor#participant`), not the actor URI.

Use cases that need the actor ID must extract it from the `CaseParticipant`'s
`attributed_to` field:

```python
participant_obj = getattr(request.activity, "object_", None)
raw_actor = getattr(participant_obj, "attributed_to", None)
actor_id = getattr(raw_actor, "id_", None) or request.object_id
```

The fallback `request.object_id` retains the `#participant` suffix and should
only be used as a last resort — log a warning if it is reached.
