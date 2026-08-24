---
source: CONCERN-2090
timestamp: '2026-08-24T18:01:52.499286+00:00'
title: CS ordering constraints (pX→PX, CP-before-ET, possible histories)
type: learning
---

# Concern: CS ordering constraints (pX→PX, CP-before-ET, possible histories) are not normatively specified

Filed during critical review of draft protocol spec §6.3.2/§6.3.3.
Three CS ordering rules existed only as code comments or non-normative references.

## Outcome

All three constraints are now normatively specified in `specs/cs-behavior.yaml` (v0.1.1).
Two are also implemented; one is structural-only; two have implementation gaps.

Docs PR: <https://github.com/CERTCC/Vultron/pull/2521>

### CP-before-ET ordering

**Spec**: CSB-12-001, CSB-04-003 — MUST record CS→P before emitting ET.
**Implementation**: Structurally enforced in `add_case_status_tree` —
`AppendCaseStatusToCaseNode` (step 4) runs before `ThreatTerminationBranchNode`
(step 6) in the BT sequence. No code change needed.

### pX→PX ephemeral invariant

**Spec**: CSB-13-001, CSB-17-003, CSB-17-012 — pXa and pXA are ephemeral
states; next CS event MUST be P.
**Implementation gap**: `ValidateCaseStatusTransitionNode` calls
`is_valid_pxa_transition` from `cs.py` (structural transitions only), which
allows A-events from pX states — violating the ephemeral constraint.
`cs_invariants.required_next_cs_events()` exists but is not called.
**Task filed**: #2524

### CS history validity

**Spec**: CSB-17-004, CSB-17-005 — complete histories must be one of 70 valid
histories; incomplete histories must be valid prefixes.
**Implementation gap**: `cs_invariants.is_valid_cs_history_prefix()` exists
but is not wired into any receive path.
**Task filed**: #2524

### ADR-0037 interaction

The interaction between CS ordering constraints and out-of-order ledger delivery
(ADR-0037 buffer/drain) is unspecified. Does the ephemeral-state guard fire on
original receipt or on replay? A new Concern is filed: #2527.

## Key discovery

Issue #2090 was filed when `specs/cs-behavior.yaml` was in scaffolding state.
By the time it was planned, CSB-17 was fully populated (v0.1.1), resolving the
normative gap. The residual work is implementation enforcement, not spec authorship.

## Root cause

The concern was legitimate at filing: the spec was at v0.0.1 scaffolding when
the concern was opened. The spec matured independently (via the behavioral
conformance specs work stream) without the concern being re-evaluated and closed.
Pattern: spec-filing and concern-triage are decoupled; concerns should be
re-triaged after major spec group additions in their domain.
