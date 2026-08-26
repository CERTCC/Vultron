---
source: CONCERN-2545
timestamp: '2026-08-26T16:06:46.415294+00:00'
title: Wire Activity artifact immutability — design
type: learning
---

Planned and documented the wire Activity artifact immutability design for CONCERN-2545.

## Key design decisions

**Inbound (A/B split):**

- A received wire Activity is a frozen artifact — it MUST NOT be mutated after construction.
- A (raw artifact) goes to `CaseLedgerEntry.payloadSnapshot` and is replicated via `Announce(CaseLedgerEntry)`.
- B (hydrated routing copy) is produced independently for dispatch and use-case execution.
- Field-type leniency (`validate_assignment=False`, ARCH-12-002) and post-construction immutability (`frozen=True`) are orthogonal properties — both MUST hold simultaneously.

**Outbound (frozen blob pipeline):**

- Factory produces a complete, frozen wire blob.
- Port interface returns the exact blob to core (not `model_dump()` dict).
- Core uses the same blob as both `payloadSnapshot` and delivery payload — no derivation.
- Ports are dumb relays; completeness belongs in the factory.

## Current gaps identified

- `TriggerActivityAdapter` returns `model_dump()` dict, not frozen blob.
- `EmitInviteActorToCaseNode._emit()` derives snapshot via `_drop_bare_inline_refs()` — not the exact emitted form.
- Three `outbound_activity.object_` mutation sites in `outbox_delivery.py` (lines 166, 236, 257) fire after ledger entry is written.

## Surfaced adjacent concern

Ledger entry is written BEFORE wire delivery (causal ordering inversion) — tracked as CONCERN-2657.
The frozen-blob design (VM-08-003) is a prerequisite for the delivery-confirmed ledger write.

## Outputs

- Docs PR: <https://github.com/CERTCC/Vultron/pull/2651>
- Spec requirements: `specs/vocabulary-model.yaml` VM-08-002 (received artifact frozen), VM-08-003 (emitted blob unchanged)
- Design note: `notes/wire-artifact-immutability.md`
- Impl issues: #2652 (frozen=True + ratchet), #2653 (port interface, size:L), #2654 (remove _drop_bare_inline_refs), #2655 (outbox delivery audit), #2656 (A/B inbox split)
- New concern: #2657 (causal ordering inversion — ledger before delivery)
