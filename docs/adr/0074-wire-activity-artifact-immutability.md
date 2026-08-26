---
status: accepted
date: 2026-08-26
deciders: ahouseholder
consulted: notes/wire-artifact-immutability.md, notes/datalayer-design.md, notes/activity-factories.md, notes/core-wire-rendering-port.md, docs/adr/0017-domain-wire-object-separation.md, docs/adr/0064-core-branch-validate-assignment.md, docs/adr/0073-per-actor-storage-isolation.md
informed: specs/vocabulary-model.yaml
---

# Treat Wire Activities as Immutable Artifacts; Freeze at Receipt and at Factory Seal

## Context and Problem Statement

Wire Activity objects (subclasses of `as_Object`) are used for two distinct
purposes that have conflicting mutability requirements:

1. **Inbound**: a received Activity is an artifact — it captures the wire state
   at receipt time. It is stored as `CaseLedgerEntry.payloadSnapshot` and
   replicated to other participants via `Announce(CaseLedgerEntry)`. Mutating
   it before ledger storage breaks replication fidelity: other actors reconstruct
   their local state from the replicated form, so they would see a different
   representation than what was originally received.

2. **Outbound**: a factory-constructed Activity is an artifact — it captures
   exactly what was sent. The same object must serve as both the delivery payload
   and the `payloadSnapshot` in the ledger entry. Adapter enrichment after the
   factory seals the blob creates a gap: the ledger records one form while the
   recipient receives another, breaking the accountability invariant.

Currently nothing in the type system prevents mutation. `as_Object` uses
`ConfigDict(validate_assignment=False)` (ADR-0064) to stay lenient for inbound
AS2 data, but has no `frozen=True`. Downstream code can and does mutate Activity
objects in place — three mutation sites in `outbox_delivery.py` overwrite
`outbound_activity.object_` after the ledger entry has already been written.

## Decision Drivers

- **Ledger integrity**: `CaseLedgerEntry.payloadSnapshot` must be identical to
  the delivered payload. Post-factory mutation creates a permanent divergence.
- **Replication fidelity**: other actors reconstruct state from the replicated
  `payloadSnapshot`. If the frozen artifact is mutated before ledger storage,
  replications propagate the mutated form.
- **Type-level enforcement**: "do not mutate" as a convention enforced only by
  documentation is insufficient; the type system should raise `TypeError` on
  accidental mutation during development and testing.
- **Orthogonality**: `validate_assignment=False` (wire branch leniency,
  ARCH-12-002) and `frozen=True` (post-construction immutability) are
  independent properties that can coexist. ADR-0064 established the former;
  this ADR establishes the latter.

## Considered Options

1. **Full `frozen=True` on `as_Object` + A/B split for inbound routing**
2. **Per-field freeze** — mark only `payloadSnapshot`-bound fields as frozen
3. **Mutable Activities with a documentation-only immutability convention**

## Decision Outcome

Chosen option: **"Full `frozen=True` + A/B split"**, because it is the only
option that enforces the invariant at the type level for both the inbound and
outbound pipelines.

### Inbound: A/B split

Two distinct objects serve the two needs of the inbound pipeline:

- **A — the frozen artifact**: the wire Activity exactly as received. Frozen
  at the moment of receipt, before any rehydration or routing logic touches it.
  Stored as `CaseLedgerEntry.payloadSnapshot`. Replicated unchanged.
- **B — the hydrated routing copy**: a separately constructed object with
  bare-string references resolved to full objects. Produced independently from
  A — not by mutating A. Used for semantic dispatch and use-case execution.
  Never stored in the ledger.

A is never modified to produce B. If rehydration fails, A remains intact.

### Outbound: frozen blob pipeline

1. **Factory** (`vultron/wire/as2/factories/`) constructs the wire object
   fully populated and returns a frozen blob.
2. **Port** (`TriggerActivityPort` / `SyncActivityPort`) returns the frozen
   blob to core — not a `model_dump()` dict.
3. **Core** uses the exact same blob for both `CaseLedgerEntry.payloadSnapshot`
   and outbox delivery.
4. **Adapter** delivers the blob unchanged — no enrichment, no expansion.

The factory is solely responsible for completeness. Adapter enrichment
compensates for an incomplete factory and creates a ledger/delivery gap.

### Consequences

- Good, because mutation of received Activities raises `TypeError` immediately
  during development, rather than corrupting ledger entries silently in
  production.
- Good, because the ledger entry and delivery payload are guaranteed identical
  — the accountability invariant becomes structurally enforced.
- Good, because `frozen=True` and `validate_assignment=False` are orthogonal;
  no change to the wire branch's lenient field-type policy is required.
- Bad, because any code that currently mutates wire Activity objects in place
  must be refactored — three known mutation sites in `outbox_delivery.py` and
  one in `EmitInviteActorToCaseNode._emit()`.
- Bad, because `TriggerActivityPort` methods must change their return type
  from `dict[str, Any]` to a frozen wire object, requiring callers to be
  updated.

## Validation

- `test/architecture/test_wire_artifact_immutability.py`: xfail tests for
  VM-08-002 and VM-08-003; promote to passing once implementation is complete.
- `specs/vocabulary-model.yaml` VM-08-002 and VM-08-003 (MUST-level requirements).

## More Information

Implementation tracked in:

- #2652 — add `frozen=True` to wire branch `as_Object` + ratchet test
- #2653 — redesign `TriggerActivityPort` to return frozen wire blob (size:L)
- #2654 — remove `_drop_bare_inline_refs` from emit nodes (blocked by #2653)
- #2655 — remove `outbox_delivery.py` enrichment mutations (blocked by #2653)
- #2656 — A/B split in inbox pipeline (blocked by #2652)

Source: CONCERN-2545. Design rationale: `notes/wire-artifact-immutability.md`.

Generated spec requirements: `specs/vocabulary-model.yaml` VM-08-002, VM-08-003.
