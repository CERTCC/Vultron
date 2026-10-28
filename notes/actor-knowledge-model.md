---
title: Actor Knowledge Model — Implementation Notes
status: active
kind: guidance
description: >
  Rules for enforcing the Actor Knowledge Model: no cross-actor DataLayer
  access, this codebase's full-inline-object rule for outbound activities (a
  prototype shortcut, not a protocol rule), the outbox last-resort guard, and
  the use-case-level actor-discovery seam, and how an actor known only by URI
  travels (AKM-05, AKM-02-006).
related_specs:
  - specs/actor-knowledge-model.yaml
  - specs/testability.yaml
  - specs/case-bootstrap-trust.yaml
relevant_packages:
  - vultron/wire/as2/factories
  - vultron/core/behaviors
  - vultron/core/use_cases
  - vultron/adapters/driving/fastapi
related_notes:
  - notes/case-bootstrap-trust.md
  - notes/spec-authoring-rules.md
---

# Actor Knowledge Model — Implementation Notes

Companion to `specs/actor-knowledge-model.yaml`.

## The Core Invariant

An Actor knows only what it has **received** via AS2 activities. There is no side
channel, no shared memory, and no DataLayer access across Actor boundaries, even
for co-located actors. Do not describe isolation as "avoiding a round-trip to the
sender's DataLayer": that framing implies the access is possible but skipped.

Corollary: **a bare object URI is resolvable only if the recipient holds the
object or can dereference it.** The protocol allows an object inline or by a
reference the recipient can fetch (AKM-02-002, AKM-03-001). This codebase
dereferences narrowly: the inbox fetches an object only for an activity no
pattern matches because of it (`UNKNOWN_UNRESOLVABLE_OBJECT`), a replica's
replaced embargo, and a proposer's profile (AKM-05-007). A bare `object` matches
no pattern that tests the object by its type (SE-01-006), so an activity whose
`object` the recipient lacks is fetched for before it reaches a handler; only
`Read(CaseLedgerEntry)`, told apart by its `ledgerPosition`, matches one. A bare
`target` or `context` still matches (SE-01-007) and its handler decides. Keep
inlining: every fetch is a round trip.

## This Codebase Carries Full Inline Objects

Inlining is a prototype shortcut, not a Vultron rule (maintainer ruling
2026-10-14, #4599; see `notes/spec-authoring-rules.md`). The project specs are
AKM-02-004 (inline every object the recipient cannot hold), AKM-03-003 (inline
every activity `object`) and AKM-02-005 (`target` reduces a case to its URI).
A ledger snapshot inlines nothing of its own: it records the activity as sent,
references included, so what a sender inlines is what the hash chain covers
(CLP-07-006, CLP-07-011).

- Pass the domain object, not its `.id_`, as `object_` and as `target` (e.g. the
  full `VulnerabilityCase` as the `target` of an `Add`); the factory reduces a
  case in `target` to its URI, or keeps a case stub (AKM-02-003, AKM-02-005).
- `actor` is an ID reference, and must be the sender's own ID.
- When in doubt, include the full object. Tracking what a peer has already seen,
  to skip redundant transmission, is a `PROD_ONLY` MAY, not prototype work.
- Builders in `vultron/core/use_cases/` and `vultron/core/behaviors/` take domain
  objects, never raw string IDs where an object is expected.
- Test fixtures that construct activities use full domain objects as `object_`
  (TB-05-004).

- An activity that introduces an object carries it inline (AKM-02-004).
  A factory whose activity class would accept an id there (a generic `as_Create`,
  or a class that admits a URI for received activities) guards it with
  `require_inline` (`vultron/wire/as2/factories/_inline.py`).

The ratchet `test/architecture/test_introduced_objects_inline.py` classifies every
factory by what it introduces and checks every example activity of an
introducing type (`Create`, `Add`, `Offer`, `Invite`, `Announce`), so a new
factory or example that sends a bare id fails it. Activities built outside the
factories escape it: grep demo and adapter code for a raw `as_*(` activity
constructor or a bare-ID `"object"` literal.

## The Outbox Guard Is a Last Resort, Not a Bridge

`vultron/adapters/driving/fastapi/outbox_delivery.py` raises
`VultronOutboxObjectIntegrityError` when an outbound initiating activity's sealed
body has a bare-string or `Link` `object`. The outbox is a dumb relay
(VM-08-003): it never expands a reference, so code must not count on anything
downstream to fill in a bare ID. If the error fires, fix the activity builder.

## AKM-05: Actor Addressing and Discovery

- **A deliverable `http(s)` URI is enough to address a peer (AKM-05-001).** A
  local `CoreActor` record is enrichment, never a precondition: under per-actor
  storage (ADR-0073) the inviter almost never holds the peer's record, so
  requiring one refuses every cross-node invitee.
- **An actor travels as held, or as an id-and-type actor reference
  (AKM-05-005, ADR-0159).** Carry the sender's held profile unchanged; with only
  the URI, carry exactly `id` and `type`. A receiver reads a reference's missing
  fields as unknown and never lets it replace a fuller record. Not a stub: it is
  the one other exception MV-10-001 allows. Factories take the held record or the
  URI (`carried_actor`, `vultron/wire/as2/factories/_actor.py`); the trigger
  adapter reads the held record first (`_held_actor`), and a bare `CoreActor`
  minimal peer travels as a reference, since its type names no wire actor.
  Marker tests: `test/wire/as2/factories/test_actor_references.py`.
- **Never record or send a value you do not know (AKM-02-006).** A clock-read
  `published`/`updated` or an `inbox`/`outbox` derived from an id is invented: a
  receiver cannot tell it from an asserted value, and a rebuild under the same id
  stops matching (OX-06-002). Leave the field absent. Delivery to a derived
  `{actor}/inbox/` is addressing, used only when no inbox is held (OX-12-009).
- **Only a hosted actor states its own endpoints.** Neither actor model derives
  `inbox`/`outbox` from the id; the node states them for the actor it hosts at
  creation (`hosted_endpoints`, `vultron/core/models/actor.py`), so its published
  profile carries both (ISSUE-3616). A peer record built with no endpoints
  passes `published=None, updated=None` too, or the base class stamps the clock.
- **Discovery is an injectable Retriever call-out (AKM-05-002).** With no local
  record, `_record_named_peer` (`vultron/core/use_cases/triggers/actor.py`) asks
  the injected `ActorDiscoveryCallOutBundle` before recording a minimal
  `CoreActor`, which holds only the id (AKM-02-006). The default,
  `ACTOR_DISCOVERY_DETERMINISTIC`, always succeeds and logs at DEBUG. A failing
  production backend logs a WARNING and still proceeds: discovery never blocks an
  invite.
- **The seam lives in the use case's `_prepare()`, not a BT node.** Recording a
  peer changes no protocol-observable state, so BT-15-001 does not apply, and a
  BT node must not be ticked procedurally outside a tree. Promote it to a BT
  subtree only if a real directory service needs async or blackboard
  interaction; the ADR-0025 bundle factory already supports that without
  changing call sites.
