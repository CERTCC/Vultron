---
title: Wire Artifact Immutability
status: active
related_specs:
  - specs/architecture.yaml (ARCH-12-001, ARCH-21-002)
  - specs/vocabulary-model.yaml (VM-08-002, VM-08-003)
related_notes:
  - notes/datalayer-design.md
  - notes/case-ledger-authority.md
  - notes/core-wire-rendering-port.md
  - notes/activity-factories.md
---

# Wire Artifact Immutability

Wire Activities that arrive or depart are **artifacts** — immutable evidence of
what was received or sent. This note codifies the design principle and its
consequences for both the inbound and outbound pipelines.

Source: CONCERN-2545.

---

## The Principle

A wire Activity is immutable once it is complete:

- **Received**: sealed at the moment of receipt, before any rehydration or
  routing logic touches it — as the received JSON text, not as a frozen object
  (see "Received evidence is a value, not a frozen graph" below).
- **Emitted**: frozen at the moment the factory seals it, before it is handed
  to any port or adapter.

Flexibility and immutability are **orthogonal**. A wire model can allow
optional fields, `Any`-typed sub-fields, and string-as-reference values (all
permitted by the lenient wire branch) while simultaneously preventing
post-construction mutation via `ConfigDict(frozen=True)`. The wire branch not
validating assignment (ADR-0064, ARCH-21-002 — it inherits nothing from the
core `CoreRecord` root that carries the flag) concerns type-checking on field
writes — it does not preclude `frozen=True`, which rejects any attribute
assignment regardless of type. Under Pydantic v2 that
rejection surfaces as a `ValidationError` with `type=frozen_instance`, not a
`TypeError`; code that means to clear a field on a wire object must build a
new one via `model_copy(update=...)` instead (issue #2904).

---

## Received Evidence Is a Value, Not a Frozen Graph

`frozen=True` on the envelope used to be the inbound guarantee, and it stopped
being one without anything failing. Pydantic's `frozen` covers only the class
that declares it, not the models nested in its fields. ADR-0099 detail 3
deleted the paired `as_*` classes, so the case, report, participant and status
inside a parsed activity are now mutable core classes. The old gate asserted
`as_Object.model_config["frozen"]` and kept passing throughout.

The nested classes cannot simply be frozen: they are also the domain objects,
mutable by design, and Pydantic has no per-instance freezing. So the evidence
moved out of the object graph:

- `parse_activity` serializes the body to JSON text **before** anything expands
  or validates it, and seals that text onto the parsed activity
  (`as_Activity.seal_received_evidence`). A `str` cannot be mutated in place,
  and `received_evidence` decodes a fresh `dict` per read, so no reader has to
  be trusted.
- The seal is write-once: resealing the same text is a no-op, and different
  text raises. It is a private attribute, which Pydantic leaves writable even
  on a frozen model, so the rule is enforced by the method, not the config.
- `FastAPIIngressAdapter.rehydrate` builds B from storage, which never kept the
  body, so it copies A's evidence onto B. Without that the evidence would stop
  at the first pipeline step.
- Replay through `StoredActivityIngressAdapter` carries no evidence yet: storage
  does not keep it. Persisting it is a step of ADR-0106 (#3742).

The gate follows the mechanism. It tampers with every class reachable in a
parsed example tree, so a class added to the vocabulary is checked the first
time an example carries it. A gate on a class flag checks the flag, not the
guarantee the flag was meant to give.

Nothing consumes the evidence yet. Recording it verbatim as the ledger's
`payloadSnapshot`, in place of today's rebuilt snapshot, is ADR-0106.

Source: ISSUE-3584.

---

## Clearing a Field: `model_copy`, Not a Cast-Silenced Assignment

To clear or override a field on a frozen wire object, build a new one with
`model_copy(update=...)`. Two things about getting there are worth carrying
forward:

- **A `cast(Any, obj).field = None` that only exists to silence a checker is a
  smell — the checker was right.** `mypy`/`pyright` pass on the assignment
  precisely because the cast erased the type that would have flagged the frozen
  target. The line can never work at runtime (`frozen=True` raises). Prefer the
  shape that needs no cast rather than casting to make an illegal assignment
  type-check.

- **Copying is correct even where in-place mutation *could* be made to work,
  because of the shared-singleton hazard.** The wire example objects (`_REPORT`,
  `_CASE`, the actors) are module-level singletons that
  `adapters/driving/fastapi/routers/examples.py` serves over HTTP. Stripping a
  field in place — via `object.__setattr__` or by dropping `frozen=True` — would
  permanently mutate the live API responses as a side effect of building the
  docs (the same class of bug that closed #1328). Returning a new object leaves
  every other holder of the instance untouched.

When probing which fields exist before copying, read `type(obj).model_fields`,
not `hasattr`: `hasattr` is also true for properties and extras, and passing
those to `model_copy(update=...)` writes a key that does not serialize.

Source: ISSUE-2904.

---

## Inbound: A/B Split

Routing and use-case execution often need a more hydrated form than raw wire
data. Two distinct objects serve these two needs:

- **A — the received artifact**: the wire Activity exactly as received. Its
  evidence is the sealed body, which nothing can mutate. The ledger replicates
  it to other participants via `Announce(CaseLedgerEntry)` so they can
  reconstruct local state from the same evidence. Today the recorded
  `payloadSnapshot` is still rebuilt from the object graph; recording the
  sealed body verbatim instead is ADR-0106.

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

The following gaps remain outstanding; the `TriggerActivityAdapter` dict-return
gap was resolved by #2652/#2653.

- `EmitInviteActorToCaseNode._call_factory()` derives `payload_snapshot` via
  `_drop_bare_inline_refs(activity_dict)` — the snapshot is not the exact
  emitted form. (Method renamed from `_emit()` by #2881.)
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
  this design principle (A/B split, dumb-relay ports). Its inbound `frozen`
  mechanism is partially superseded by ADR-0099 (see above).
- **ADR-0106** (proposed): a case ledger entry is a postmark on the received
  envelope; replicas resolve bare references by dereference.
- **ADR-0017**: two-branch hierarchy (core branch strict, wire branch
  lenient). Its shared root is gone: under ADR-0099 detail 4 `as_Base` stands
  on `pydantic.BaseModel` directly and inherits nothing from core
  (ARCH-12-001). Wire branch flexibility does not preclude wire branch
  immutability.
- **ADR-0064**: the wire branch does not validate assignment — it never
  inherits `validate_assignment` from the core `CoreRecord` root
  (ARCH-21-002). Orthogonal to `frozen=True`.
- **ADR-0073**: per-actor DataLayer isolation — each actor's artifact store
  holds only what that actor received, preserving each actor's independent view.

## Related Notes

- `notes/datalayer-design.md` — "Received Activity Artifacts" section:
  rationale for non-recursive dehydration of inline Activity sub-fields.
- `notes/core-wire-rendering-port.md` — `WireRenderPort` driven seam: how core
  obtains wire-shaped JSON without importing wire types.
- `notes/activity-factories.md` — factory function inventory and construction
  patterns.
