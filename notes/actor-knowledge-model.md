---
title: Actor Knowledge Model — Implementation Notes
status: active
kind: guidance
description: >
  Rules for enforcing the Actor Knowledge Model: no cross-actor DataLayer
  access, full inline objects in outbound activities, the outbox last-resort
  guard, and the use-case-level actor-discovery seam (AKM-05).
related_specs:
  - specs/actor-knowledge-model.yaml
  - specs/testability.yaml
relevant_packages:
  - vultron/core/behaviors
  - vultron/core/use_cases
  - vultron/adapters/driving/fastapi
related_notes:
  - notes/case-bootstrap-trust.md
---

# Actor Knowledge Model — Implementation Notes

Companion to `specs/actor-knowledge-model.yaml`.

## The Core Invariant

An Actor knows only what it has **received** via AS2 activities. There is no side
channel, no shared memory, and no DataLayer access across Actor boundaries, even
for co-located actors. Do not describe isolation as "avoiding a round-trip to the
sender's DataLayer": that framing implies the access is possible but skipped.

Corollary: **an outbound activity that carries a bare object URI cannot be
resolved by its recipient.** Rehydration from the recipient's own store fails and
pattern matching falls through to `MessageSemantics.UNKNOWN`.

## Outbound Activities Carry Full Inline Objects

- Pass the domain object, not its `.id_`, as `object_` and as `target` (e.g. the
  full `VulnerabilityCase` as the `target` of an `Add`). The one approved
  exception is the stub object in `Invite.target`.
- `actor` is an ID reference, and must be the sender's own ID.
- When in doubt, include the full object. Tracking what a peer has already seen,
  to skip redundant transmission, is a `PROD_ONLY` MAY, not prototype work.
- Builders in `vultron/core/use_cases/` and `vultron/core/behaviors/` take domain
  objects, never raw string IDs where an object is expected.
- Test fixtures that construct activities use full domain objects as `object_`
  (TB-05-004).

To audit, grep activity construction for `object_=.*\.id_` and `target=.*\.id_`,
and check demo dict literals for bare-ID `"object"` values.

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
- **Discovery is an injectable Retriever call-out (AKM-05-002).** With no local
  record, `_record_named_peer` (`vultron/core/use_cases/triggers/actor.py`) asks
  the injected `ActorDiscoveryCallOutBundle` before minting a minimal
  `CoreActor`. The default, `ACTOR_DISCOVERY_DETERMINISTIC`, always succeeds and
  logs at DEBUG. A failing production backend logs a WARNING and still proceeds:
  discovery never blocks an invite.
- **The seam lives in the use case's `_prepare()`, not a BT node.** Recording a
  peer changes no protocol-observable state, so BT-15-001 does not apply, and a
  BT node must not be ticked procedurally outside a tree. Promote it to a BT
  subtree only if a real directory service needs async or blackboard
  interaction; the ADR-0025 bundle factory already supports that without
  changing call sites.
