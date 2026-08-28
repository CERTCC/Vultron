---
source: CONCERN-2595
timestamp: '2026-08-26T17:19:02.208994+00:00'
title: Split VFD state machine into vendor-path and deployer-path sub-machines
type: learning
---

## Concern

CS_vfd couples the vendor-path (v→V, f→F) and deployer-path (d→D) transitions in a
single 4-state chain, making the data model ambiguous about which transitions apply
to a given participant role. The immediate workaround (CSB-15-004 causal gate, #2593)
addresses the symptom at the guard layer; the structural concern is whether the state
machine should be split.

## Decision

Split at the per-participant level (Direction 3a). `CS_vfd` / `VfdDimension` are
replaced by two separate sub-machines:

- **Vendor path** (`CS_vf`, 3 states: `vf` → `Vf` → `VF`): only for VENDOR participants
- **Deployer path** (`CS_d`, 2 states: `d` → `D`): only for DEPLOYER participants

`ParticipantStatus.vfd` becomes two nullable fields:

- `vf: VfDimension | None = None` — `None` for non-VENDOR participants (structural)
- `d: DDimension | None = None` — `None` for non-DEPLOYER participants (structural)

A `model_validator(mode='after')` enforces both directions of the role-dimension
invariant at construction time and raises `VultronValidationError` on violation.
The old `CS_vfd.vfd` null-element workaround for non-applicable participants is
superseded by structural `None`.

CSB-15-001 (VENDOR required for f→F) and CSB-15-002 (DEPLOYER required for d→D)
become structurally enforced at object-construction time rather than BT guard checks.
CSB-15-004 (d→D only if some vendor has `vf.state=VF`) remains a cross-participant
BT guard.

Wire format: `vfd_state` removed; replaced by `vf_state: CS_vf | None` and
`d_state: CS_d | None`. No backward-compat migration shim.

`cs_invariants.py` event-sequence logic is unchanged — V/F events originate from `vf`
dimension transitions and D events from `d` dimension transitions; the sequence
constraints remain valid at the case-history level.

## Out of scope

Fine-grained vendor-deployer dependency tracking (which specific vendor does a given
deployer depend on before they can deploy) is not tracked anywhere. The generic
CSB-15-004 gate ("some vendor at VF") is the correct bound for now. A follow-on
Concern is open at #2665.

## Implementation ratchet chain

Three sequenced Task issues (each leaves system green):

- #2662 — Add `CS_vf`, `CS_d`, `VfDimension`, `DDimension` (additive, size:S)
- #2663 — Split `ParticipantStatus.vfd` into `vf`/`d`, migrate all call sites (size:L)
- #2664 — Remove `CS_vfd`, `VfdDimension`, retired guard nodes (size:S)

## Reference

Docs PR: <https://github.com/CERTCC/Vultron/pull/2661>
Follow-on Concern: #2665
