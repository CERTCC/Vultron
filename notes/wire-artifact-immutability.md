---
title: Wire Artifact Immutability
status: active
kind: guidance
description: >
  Wire activities that arrive or depart are immutable evidence: received bodies
  are sealed as JSON text at parse, emitted ones as the factory's sealed body.
  Covers the inbound A/B split, clearing a field with model_copy, and why
  delivery ports are dumb relays.
related_specs:
  - specs/architecture.yaml (ARCH-12-001, ARCH-21-002, ARCH-25-003)
  - specs/vocabulary-model.yaml (VM-08-002, VM-08-003)
  - specs/outbox.yaml (OX-07-001)
  - specs/case-ledger-processing.yaml (CLP-07-011)
  - specs/case-management.yaml (CM-17-002)
  - specs/message-validation.yaml (MV-10-001)
related_notes:
  - notes/datalayer-design.md
  - notes/case-ledger-authority.md
  - notes/core-wire-rendering-port.md
  - notes/activity-factories.md
  - notes/outbox.md
related_adrs:
  - ADR-0074
  - ADR-0107
  - ADR-0119
---

# Wire Artifact Immutability

A wire activity that arrives or departs is an **artifact**: immutable evidence of
what was received or sent (ADR-0074).

- **Received**: sealed at receipt, before rehydration or routing touches it, as
  the received JSON text.
- **Emitted**: sealed when the factory builds it, before any port or adapter
  sees it.

Flexibility and immutability are orthogonal. The lenient wire branch (optional
fields, `Any`, string references, no `validate_assignment`, ARCH-21-002) still
allows `ConfigDict(frozen=True)`. Under Pydantic v2 a write to a frozen model
raises `ValidationError` with `type=frozen_instance`, not `TypeError`.

## Received Evidence Is a Value, Not a Frozen Graph

Pydantic's `frozen` covers only the class that declares it, not models nested in
its fields, and the case, report, participant and status inside a parsed activity
are mutable core classes (ARCH-25-003). So the evidence lives outside the object
graph (VM-08-002):

- `parse_activity` serializes the body to JSON text **before** anything expands
  or validates it and seals it with `as_Activity.seal_received_evidence`.
  `received_evidence` decodes a fresh `dict` per read, so no reader has to be
  trusted.
- The seal is write-once: resealing the same text is a no-op, different text
  raises. It is a private attribute, which Pydantic leaves writable even on a
  frozen model, so the method enforces the rule, not the config.
- `FastAPIIngressAdapter.rehydrate` builds B from storage, which never kept the
  body, so it copies A's evidence onto B; without that the evidence stops at the
  first pipeline step.

**Gate the guarantee, not the flag.** The immutability test tampers with every
class reachable in a parsed example tree, so a new vocabulary class is checked
the first time an example carries it. A test asserting
`model_config["frozen"]` kept passing after the guarantee was gone.

The evidence does not reach core: the extractor builds the `VultronEvent`, which
has no evidence field. The receive-side ledger snapshot is a rendering of the
extractor's rebuilt `VultronActivity`, the "canonical normalization" branch of
CLP-07-011, not the verbatim body; an emitted entry records the factory's sealed
blob. Recording received evidence verbatim, and persisting it for replay, is
ADR-0107 (#3742).

## Clearing a Field: `model_copy`, Not a Cast-Silenced Assignment

To clear or override a field on a frozen wire object, build a new one with
`model_copy(update=...)`.

- **A `cast(Any, obj).field = None` that exists to silence a checker means the
  checker was right.** The cast erased the type that flagged the frozen target;
  the line raises at runtime.
- **Copy even where in-place mutation could be made to work.** The wire example
  objects (`_REPORT`, `_CASE`, the actors) are module-level singletons served
  over HTTP by `adapters/driving/fastapi/routers/examples.py`; mutating one in
  place (`object.__setattr__`, or dropping `frozen=True`) permanently changes
  live API responses (#1328).
- Probe fields with `type(obj).model_fields`, not `hasattr`: `hasattr` is also
  true for properties and extras, and `model_copy(update=...)` then writes a key
  that does not serialize.

## Inbound: A/B Split

- **A, the received artifact**: the activity exactly as received; its evidence is
  the sealed body.
- **B, the hydrated routing copy**: built independently from A with references
  resolved, used for dispatch and use-case execution, never stored in the
  ledger.

A is never modified to produce B; if rehydration fails, A is intact. Replicas
receive A via `Announce(CaseLedgerEntry)` and build their own B, so mutating A
would propagate a form no other actor can reconcile with what was received.

## Outbound: Frozen Blob Pipeline

1. Core builds or requests the domain object for the activity.
2. The factory (`vultron/wire/as2/factories/`) builds the fully populated wire
   object (case stub with embargo enrichment, every required field).
3. The port (`TriggerActivityPort` / `SyncActivityPort`) returns
   `(activity_id, activity_blob)` to core, an opaque blob, not a `model_dump()`
   dict (VM-08-003).
4. Core uses the **same blob** for `CaseLedgerEntry.payloadSnapshot` and for
   delivery.
5. The adapter delivers it as-is: no enrichment, no ref expansion, no hydration.

Commit ordering against the outbox write is ADR-0119.

### How the blob reaches delivery: the sealed body

The outbox queues activity ids, and the activity *record* the DataLayer holds is
not the blob: persistence dehydrates references and read-back rehydrates them
from the current store. Delivering the record collapsed an Invite's enriched case
stub (CM-17-002) to a bare URI (#2624).

So the blob has its own record: `SealedOutboundBody`
(`vultron/adapters/outbox_sealed_body.py`), the factory object's
`model_dump_json` text keyed by activity id. Every adapter that persists an
outbound activity seals it at that moment (`TriggerActivityAdapter._seal`, the
sync adapter, the outbox route, the pending-case queue, the pending-create
retry), and the sealed text is the `activity_blob` returned to core. The outbox
handler reads the sealed body, applies only the last-resort guards (`to:`
present, inline `object`), and hands the text to the emitter unchanged; nothing
on the delivery path reads the activity record (OX-07-001). Sealing is
write-once per activity id.

Consequences for core:

- An emit node records `json.loads(activity_blob)` as its `payloadSnapshot`,
  unpatched. The factory sets `context` to the case URI and reduces a full case
  `target` to its URI (`factories/_context.py`); only the Invite's stub stays an
  object (MV-10-001).
- An activity core would build itself (the CaseProposal `Accept`, the prepared
  `Create(VulnerabilityCase)`, the CM-06-001 update broadcast) goes through the
  trigger port, because only the adapter can seal it.

## Why "Ports Are Dumb Relays"

The factory produces a complete, self-contained blob. Adapter-side enrichment
compensates for an incomplete factory and opens an integrity gap: the ledger
records the pre-enrichment blob while the recipient receives another, so
recipients and replicas see different representations of one event. Fix the
factory instead.
