---
title: Wire Artifact Immutability
status: active
related_specs:
  - specs/architecture.yaml (ARCH-12-001, ARCH-21-002)
  - specs/vocabulary-model.yaml (VM-08-002, VM-08-003)
  - specs/outbox.yaml (OX-07-001, OX-07-002)
  - specs/case-ledger-processing.yaml (CLP-07-011, CLP-02-003)
related_notes:
  - notes/datalayer-design.md
  - notes/case-ledger-authority.md
  - notes/core-wire-rendering-port.md
  - notes/activity-factories.md
  - notes/outbox.md
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
  does not keep it. Persisting it is a step of ADR-0107 (#3742).

The gate follows the mechanism. It tampers with every class reachable in a
parsed example tree, so a class added to the vocabulary is checked the first
time an example carries it. A gate on a class flag checks the flag, not the
guarantee the flag was meant to give.

Nothing consumes the evidence yet, and it does not reach core. The evidence is
sealed on the wire `as_Activity`; `prepare_for_dispatch` builds the
`VultronEvent` from it through the extractor, the event has no evidence field,
and the dispatcher sees only the event. What core holds is the extractor's
rebuilt `VultronActivity`, which keeps a chosen subset of fields, so the
receive-side ledger snapshot is a rendering of that subset — CLP-07-011's
"deterministic canonical normalization" branch, not its "verbatim" one — while
an emitted entry already records the factory's sealed blob (VM-08-003). For
activities that were actually sent, the CASE_MANAGER's ledger therefore carries
two snapshot provenances until ADR-0107 step 5 (#3742) records the evidence
verbatim, which first has to carry it onto the event at the parse edge
(ISSUE-3947). The hand-built Lapse and case-closed entries are a third, which
step 6 (#3743) turns into emitted activities.

Source: ISSUE-3584, ISSUE-3947.

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
  sealed body verbatim instead is ADR-0107.

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

### How the blob reaches delivery: the sealed body

The outbox is a queue of activity ids, and the activity *record* the DataLayer
holds is not the blob: persistence dehydrates reference fields to ids, and
read-back rehydrates them from whatever the store holds now.  So the record is
a reconstruction, and delivering it is how the ledger and the wire came to
disagree — an Invite's enriched case stub (CM-17-002) was collapsed to a bare
URI on its way out (#2624).

The blob therefore has its own record.  `vultron/adapters/outbox_sealed_body.py`
holds `SealedOutboundBody`: the factory object's `model_dump_json` text, stored
under an id derived from the activity id.  Every adapter that persists an
outbound activity seals it at the same moment — `TriggerActivityAdapter._seal`
ends every method, and the sync adapter, the outbox route, the pending-case
queue and the pending-create retry seal theirs — and the text sealed is the
`activity_blob` returned to core.  The outbox handler reads the sealed body,
applies only the last-resort guards (`to:` present, inline `object`), and hands
the text to the emitter unchanged.  Nothing on the delivery path reads the
activity record any more (OX-07-001).

Two consequences for core:

- an emit node records `json.loads(activity_blob)` as its `payloadSnapshot`,
  with no stripping or patching — the factory sets `context` to the case URI
  and reduces a full case handed in as `target` to its URI
  (`factories/_context.py`: `with_case_context`, `case_target_ref`; only the
  Invite's selective-disclosure stub stays an object, MV-10-001), and the
  commit boundary accepts a bare `target` that names the entry's own case,
  because the factories address a case by its URI (AKM-02-003) and every
  replica holds it;
- an activity core used to build itself (the CaseProposal `Accept`, the
  prepared `Create(VulnerabilityCase)`, the CM-06-001 update broadcast) goes
  through the trigger port instead, because only the adapter can seal it.

Sealing is write-once per activity id: a re-emission under an id the store
already holds gets the body that was, or will be, delivered.

The received side is not yet at parity: a receiver's ledger entry is still
rebuilt from its object graph (ADR-0107 step 5, #3742).

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
- **ADR-0107** (proposed): a case ledger entry is a postmark on the received
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
