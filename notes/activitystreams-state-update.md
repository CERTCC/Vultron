---
title: "ActivityStreams: Case State Update and Advanced Patterns"
status: active
kind: guidance
description: >
  Case state update path and CASE_MANAGER authoritativeness, outbound activity
  naming and addressing, unresolvable-object dead letters, serialization and
  parsing traps, the bootstrap embedded-object contract, and semantic registry
  pattern rules.
related_specs:
  - specs/semantic-extraction.yaml
  - specs/response-format.yaml
  - specs/case-management.yaml
  - specs/handler-protocol.yaml
  - specs/case-bootstrap-trust.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/bt-integration.md
relevant_packages:
  - pydantic
  - vultron/wire/as2
  - vultron/core/models/events
---

# ActivityStreams: Case State Update and Advanced Patterns

See also [activitystreams-semantics.md](activitystreams-semantics.md).

## The CASE_MANAGER Is the Authoritative Case State

An actor's local `VulnerabilityCase` is a cached projection. Case-state changes
flow actor → CASE_MANAGER inbox → canonical update → broadcast to every
participant → each participant updates its copy. A participant does not accept
case state from another regular actor, so the CASE_MANAGER stays the single
coordination point and replicas cannot diverge (CM-06-002). In production the
participant must also authenticate that the update came from the CASE_MANAGER
(`PROD_ONLY`, CM-06-004).

## Outbound Activity `name` Is Semantic Content

Derive a BT-built activity's `name` from the object's own attributes
(`object_.name or object_.id_`), never `repr()` or `str()`. The outbound adapter
does not sanitize semantic content.

## A `cc`-Only Receiver of `Offer(Report)` Refuses It

Only a `to` recipient of `Offer(Report)` creates a case; a `cc`-only receiver
reports `REFUSED` with a reason naming the addressing (HP-01-005, HP-09-001).

## An Unresolvable `object_` Is a Dead Letter, Not a Missing Pattern

A bare URI still in `object_` after rehydration resolves to
`UNKNOWN_UNRESOLVABLE_OBJECT`, not `UNKNOWN`: no registered pattern is a code
gap, whereas an unresolvable object is a data gap.
`UnresolvableObjectUseCase` (`vultron/core/use_cases/received/unknown.py`) logs
a WARNING and stores a dead-letter record (VAM-01-009).

## `Accept(Invite)` Carries the Invite

The `object_` of an `Accept(Invite(...))` is the original `Invite` activity,
not the case or embargo event; a wrong object fails coercion at the receiver.
Set `inReplyTo` on the accept/reject models themselves, defaulting from the
Invite, rather than relying on every call site to wire it.

## Put Activity-Family Requirements on the Shared Base Type

When a field is required across an AS2 activity family, the shared base type
encodes it. Use the required alias (`ActivityStreamRequiredRef`), not just a
changed `Field(...)` default: `ActivityStreamRef` still admits `None`, so the
type-level and runtime contracts would diverge.

## Base-Typed Fields Drop Inline Subtype Fields Without `serialize_as_any`

A nested value stored through a base reference annotation
(`as_ObjectRequiredRef`) serializes as the base shape under plain
`model_dump()`, silently omitting subtype-only fields. Paths that revalidate or
deliver rehydrated activities use `model_dump(..., serialize_as_any=True)`.
Regression tests must cover both the persistence boundary and the outbound
delivery boundary: a DataLayer round trip alone misses loss in the outbox.

## Parsing Recurses Into Nested Inline Activities

`Accept(Invite(...))` nests an `Invite` whose own `actor` and `object_` must also
be parsed to typed objects, or `ActivityPattern` matching on subtypes fails. A
case stub is recognized by its `type` (`VulnerabilityCaseStub`, CM-11-013),
never by its sparseness: a sparse `VulnerabilityCase` is always a case.

## Bootstrap Embeds Nested Objects Inline

Every nested domain object in a `Create(VulnerabilityCase)` bootstrap (for
example the `case_participants` records) MUST be a full inline object, never a
URI string (CBT-01-007). `ActivityStreamRef` accepts the string, but the
receiver persists only materialized entries, so the participant is never stored
and later participant guards fail. Serialize the snapshot with
`serialize_as_any=True` (see above).

## Registry Patterns Match the Inbound Wire Format

A semantic registry pattern matches what arrives in the **receiver's** inbox, not
what this actor emits. Before adding an entry, ask who sends the message and what
the recipient receives. `OfferActorToCasePattern` (`Offer(CaseParticipant,
Case)`) stays in `_instances.py` only as a nested template for the actor
recommendation patterns; `OFFER_ACTOR_TO_CASE` matches `SuggestActorToCasePattern`
(`Offer(Actor, Case)`).

## `offer_case_participant_activity` Object IDs Carry `#participant`

The factory builds the `CaseParticipant` with `id_=f"{actor_id}#participant"`,
so the extracted `object_id` is the participant URI, not the actor. Read the
actor from the participant's `attributed_to`; falling back to `object_id` keeps
the suffix, so log a warning if it is reached.

## Roles Come From the Stored Offer the CASE_MANAGER Sent

On `Accept(Offer(CaseParticipant))`, the CASE_MANAGER reads the invitee's roles
from the stored Offer it constructed, never from the participant embedded in
the Accept: the acceptor could substitute or omit roles (ADR-0026). See
`vultron/core/use_cases/received/actor/offer_case_participant.py`.

## Patterns Sharing a Verb and Object Need a Strict Discriminator

`target_` is matched permissively unless the pattern sets `strict=True`, so a
bare URI target matches any typed target constraint. A new semantic that shares
an `(activity_, object_)` pair with an existing pattern MUST either use a
distinct object type (preferred, SE-08-003) or add a more specific discriminator
with `strict=True` and sit before the less specific entry in `SEMANTIC_REGISTRY`
(SE-08-001, SE-08-004).
