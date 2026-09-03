---
source: CONCERN-3008
timestamp: '2026-09-03T16:20:22.315009+00:00'
title: PXA↔EM entailment enforcement path
type: learning
---

## Concern

CSB-18-002..004 require that a participant's composite state MUST NOT have P, X,
or A bits set while an active embargo exists. The function
`violation_pxa_em_entailment()` (cross_machine_invariants.py) was written to
detect this contradiction but had zero production callers. The concern was that
there was "no enforcement path."

## Resolution

The enforcement path already exists — it was just undocumented and partially
blocked:

- **`ThreatTerminationBranchNode`** in `add_case_status_tree` fires embargo
  teardown when the received CaseStatus carries any of P=True, X=True, or A=True
  and an active embargo exists. This handles P, X, and A arrivals (including the
  ephemeral pX→PX case, where `CheckCsEphemeralStateNode` enforces the X→P
  advance).
- The **FastAPI adapter** already wires `STATUS_AUTHORIZATION_PERMISSIVE`
  (AlwaysSucceed) for the `EmbargoTeardownAuthorizationGate`, so teardown fires
  automatically in production.
- The **function default** for `add_case_status_tree` is
  `STATUS_AUTHORIZATION_DETERMINISTIC` (`RequireCaseOwnerApprovalNode`, always
  FAILURE) — teardown is blocked when the default is used directly, e.g., in
  unit tests.

## What was wrong

1. `violation_pxa_em_entailment()` has no production callers — so there is no
   runtime diagnostic when the gate blocks teardown and the invariant remains
   violated.
2. The docstring in `add_case_status_tree.py` incorrectly said "Default is
   AlwaysSucceed" — backwards in both claims (default blocks; FastAPI permits).
3. The CSB-18-002..004 spec rationale said "Implemented in
   violation_pxa_em_entailment()" — misleading because that function is a
   diagnostic, not the enforcement mechanism.

## What was fixed (this PR)

- Corrected the `add_case_status_tree.py` docstring.
- Updated CSB-18 group description and CSB-18-002..004 rationale to name
  `ThreatTerminationBranchNode` as the enforcement mechanism and
  `violation_pxa_em_entailment()` as the unhooked diagnostic.
- Added a note in `notes/received-status-authorization.md` linking
  CSB-18-002..004 to the enforcement gap.

## What remains

Impl issue #3115 tracks wiring `violation_pxa_em_entailment()` as a post-cascade
diagnostic: when the gate blocks teardown and the invariant is still violated,
post a Note to the case. Integration tests cover both paths (clean and violation).
Protocol-ask routing subtree replacement for the gate is tracked by #2885.

## PR

<https://github.com/CERTCC/Vultron/pull/3114>
