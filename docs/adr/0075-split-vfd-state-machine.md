---
status: accepted-provisional
date: 2026-08-26
deciders: Allen D. Householder
consulted: []
informed: []
---

# Split Per-Participant VFD Tracking into Separate Vendor-Path and Deployer-Path Sub-Machines

## Context and Problem Statement

The `CS_vfd` sub-machine couples vendor-awareness (`v→V`), fix-readiness
(`f→F`), and fix-deployment (`d→D`) transitions into a single 4-state chain
(`vfd → Vfd → VFd → VFD`) for all participants regardless of their CVD role.
This creates a semantic mismatch: `V` and `F` transitions are only meaningful for
VENDOR participants (who develop and supply fixes), while `D` transitions are only
meaningful for DEPLOYER participants (who apply fixes in their own environments).

For a DEPLOYER-only participant the `vfd` field could never advance past `vfd`
through normal V/F transitions, requiring a workaround: the `CS_vfd.vfd` null
element doubled as both "initial state" and "not applicable". This workaround
was addressed at the guard layer (CSB-15-004 causal gate, PR #2593) but left the
data-model ambiguity in place. See CONCERN-2595 for the full context.

## Decision Drivers

- The `CS_vfd.vfd` "null element" was overloaded: it meant both "vendor unaware,
  fix not ready, not deployed" (initial state for VENDORs) and "not applicable"
  (for DEPLOYER-only and non-VFD participants).
- BT guards compensated for data-model ambiguity rather than preventing
  structurally impossible states.
- A participant's permitted transitions should be derivable from its role without
  runtime guards.

## Considered Options

- **Direction 1** — keep `CS_vfd` monolithic; enforce via guards only
- **Direction 2** — add a role predicate to `ParticipantStatus` to gate VFD
  sub-field access at runtime
- **Direction 3a** — split at the per-participant level into two nullable fields:
  `vf: VfDimension | None` (vendor path, 3 states) and `d: DDimension | None`
  (deployer path, 2 states); structural `None` for inapplicable roles
- **Direction 3b** — split `CS_vfd` into a compound type with optional V/F and
  optional D parts at the case-aggregate level

## Decision Outcome

Chosen option: **Direction 3a** — split at the per-participant level with two
nullable fields on `ParticipantStatus`.

Rationale: structural `None` makes role-based inapplicability unrepresentable
rather than merely rejected at runtime. A DEPLOYER-only participant literally
cannot have a `vf` value (it is `None`); a VENDOR-only participant cannot have a
`d` value. This eliminates the guard-compensating pattern for role checks on these
dimensions. Direction 1 leaves the ambiguity intact. Direction 2 adds runtime
predicates without removing the ambiguous field. Direction 3b changes the
case-aggregate CS model, which is orthogonal and unnecessary — the compound
`CS_vfd` (4 states) at the case level is unchanged.

The implementation is sequenced as three additive+removable tasks:

- #2662 — Add `CS_vf`, `CS_d`, `VfDimension`, `DDimension` (additive)
- #2663 — Migrate `ParticipantStatus.vfd` to `vf`/`d` fields
- #2664 — Remove `CS_vfd`, `VfdDimension`, and retired guard nodes

Status is `accepted-provisional` because implementation is not yet complete;
the spec changes and model_validator contract are the validated direction, but
the final shape may be refined during #2663.

### Consequences

- Good, because role-based inapplicability becomes structural — no guard needed
  for "does this participant have a vendor path?"
- Good, because `ParticipantStatus` construction validates role-dimension
  invariants at object-creation time, raising `VultronValidationError` on
  violation rather than silently accepting impossible states.
- Good, because the case-level `CS_vfd` 4-state enum and `cs_invariants.py`
  history validity logic are unchanged — the split is per-participant only.
- Bad, because migration of all `ParticipantStatus.vfd_state` call sites (#2663)
  is a large mechanical change requiring careful review.
- Neutral, because the compound CS state (VFD × PXA, 32 members) is unaffected;
  `CSB-17-001` remains valid.

## Validation

Validated by the `model_validator(mode='after')` on `ParticipantStatus` that
enforces the role-dimension invariant table (see `notes/case-state-model.md`
§ "Role-Specific VFD Access"). Implementation tasks #2662–#2664 will add unit
tests confirming that construction with a violated invariant raises
`VultronValidationError`.

## More Information

- Planning learning: `plan/history/2608/learning/CONCERN-2595.md`
- Follow-on concern (fine-grained vendor-deployer dependency tracking): #2665
- Immediate workaround (guard layer): PR #2593, CONCERN-2595

Generated spec requirements: `specs/cs-behavior.yaml` CSB-15-001, CSB-15-002,
CSB-15-004, CSB-16-001.
