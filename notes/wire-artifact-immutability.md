---
title: Wire Artifact Immutability
status: active
---

# Wire Artifact Immutability

Wire Activities that arrive or depart are **artifacts** — immutable evidence of
what was received or sent. This note codifies the design principle and its
consequences for both the inbound and outbound pipelines.

Source: CONCERN-2545.

---

## The Principle

A wire Activity is immutable once it is complete:

- **Received**: frozen at the moment of receipt, before any rehydration or
  routing logic touches it.
- **Emitted**: frozen at the moment the factory seals it, before it is handed
  to any port or adapter.

Flexibility and immutability are **orthogonal**. A wire model can allow
optional fields, `Any`-typed sub-fields, and string-as-reference values (all
required by the lenient wire branch per ARCH-12-002) while simultaneously
preventing post-construction mutation via `ConfigDict(frozen=True)`. The
`validate_assignment=False` exemption on `as_Object` (ADR-0064) affects
type-checking on field writes — it does not preclude `frozen=True`, which
raises `TypeError` on any attribute assignment regardless of type.

---

## Inbound: A/B Split

Routing and use-case execution often need a more hydrated form than raw wire
data. Two distinct objects serve these two needs:

- **A — the frozen artifact**: the wire Activity exactly as received. Never
  mutated. Stored as `CaseLedgerEntry.payloadSnapshot`. Replicated to other
  participants via `Announce(CaseLedgerEntry)` so they can reconstruct local
  state from the same evidence.

- **B — the hydrated routing copy**: a separately constructed object with
  bare-string references resolved to full objects. Produced independently from
  A — not by mutating A. Used for semantic dispatch and use-case execution.
  Not stored in the ledger.

A is never modified to produce B. If rehydration fails and B cannot be
produced, A remains intact and untouched.

**Replication fidelity**: other actors receive A via `Announce(CaseLedgerEntry)`
and reconstruct their own B locally. If A were mutated before ledger storage,
replication would propagate the mutated form, and other actors could not
reconstruct the original received state.

---

## Outbound: Frozen Blob Pipeline

The canonical outbound pipeline:

1. **Core** builds or requests a domain object representing the activity.
2. **Factory** (`vultron/wire/as2/factories/`) constructs the wire object,
   fully populated (case stub with embargo enrichment, all required fields).
   The result is a frozen wire blob.
3. **Port interface** (`TriggerActivityPort` / `SyncActivityPort`) returns the
   frozen blob — not a `model_dump()` dict — to core. Core must not import wire
   types; the blob is opaque at the port boundary (raw JSON or an opaque bytes
   value).
4. **Core** receives `(activity_id, frozen_blob)`. It uses the **exact same
   blob** for:
   - `CaseLedgerEntry.payloadSnapshot` — what was recorded
   - Outbox delivery payload — what was sent
5. **Port/adapter** delivers the blob as-is. No enrichment, no expansion of
   bare refs, no hydration of inline objects. The adapter is a **dumb relay**.

The ledger entry is written only after successful delivery — see the causal
ordering concern (CONCERN-2546).

### Current gaps (as of CONCERN-2545)

- `TriggerActivityAdapter` returns `model_dump()` dict, not a frozen blob.
- `EmitInviteActorToCaseNode._emit()` derives `payload_snapshot` via
  `_drop_bare_inline_refs(activity_dict)` — the snapshot is not the exact
  emitted form.
- Three mutation sites in `outbox_delivery.py` (lines 166, 236, 257) overwrite
  `outbound_activity.object_` after the ledger entry has been written.

These gaps are tracked as implementation tasks under CONCERN-2545.

---

## Why "Ports Are Dumb Relays"

The factory is responsible for producing a complete, self-contained wire blob.
Adapter code that enriches an outbound activity (expanding refs, hydrating
inline objects) is compensating for an incomplete factory — the enrichment
belongs at construction time, not delivery time.

Moving enrichment into the adapter creates an integrity gap: the ledger records
the pre-enrichment blob while the recipient receives the post-enrichment one.
Recipients and replicants therefore see different representations of the same
event, breaking the accountability invariant.

---

## ADR Cross-references

- **ADR-0074**: wire Activity artifact immutability — the decision record for
  this design principle (frozen=True on wire branch, A/B split, dumb-relay ports).
- **ADR-0017**: two-branch hierarchy (`VultronBase` shared root, core branch
  strict, wire branch lenient). Wire branch flexibility does not preclude wire
  branch immutability.
- **ADR-0064**: `validate_assignment=False` on wire branch — exempts wire
  branch from post-construction type validation. Orthogonal to `frozen=True`.
- **ADR-0073**: per-actor DataLayer isolation — each actor's artifact store
  holds only what that actor received, preserving each actor's independent view.

## Related Notes

- `notes/datalayer-design.md` — "Received Activity Artifacts" section:
  rationale for non-recursive dehydration of inline Activity sub-fields.
- `notes/core-wire-rendering-port.md` — `WireRenderPort` driven seam: how core
  obtains wire-shaped JSON without importing wire types.
- `notes/activity-factories.md` — factory function inventory and construction
  patterns.
