---
source: NOTES-behavioral-conformance-specs--key-ordering-constraints-captured
timestamp: '2026-10-12T23:47:25.777960+00:00'
title: 'Behavioral conformance specs: key ordering constraints (now normative in CSB/CLP)'
type: note
---

Archived from `notes/behavioral-conformance-specs.md` by #4497 (notes sweep): the
ordering constraints are normative in the specs they cite (CSB-12-001,
CSB-04-003, CSB-13-001, CSB-17-003/004/005/012, VP-06-007, and
`specs/case-ledger-processing.yaml` CLP-10-006 with ADR-0111). The node-level
enforcement notes describe code in `vultron/core/behaviors/status/`, which is the
authority for how they are met.

---

## Key Ordering Constraints Captured

Some ECA rules are not just "do A when B" but "do A *before* B." These use
`steps:` on `BehavioralSpec` items to encode ordering. Critical ones:

- **CS→P triggers embargo teardown** (CSB-12-001, CSB-04-003): record CS state
  transition *first*, then initiate teardown. Observable: CP must precede ET in
  the message stream. This is normatively specified as MUST and is also enforced
  structurally in `add_case_status_tree` (AppendCaseStatusToCaseNode runs before
  ThreatTerminationBranchNode).
- **Ephemeral states: pX→PX invariant** (CSB-13-001, CSB-17-003, CSB-17-012):
  when the CS PXA state is pXa or pXA (exploit public without public awareness),
  the next CS event MUST be P. **Write-boundary enforcement** (AC-1, PR #2479):
  `promote_pxa()` (`case_status_snapshot.py`), called by `AppendCaseStatusToCaseNode`
  and `EmitCaseStatusUpdateNode`,
  and `_apply_ac1_promotions()` in `CreateParticipantStatusNode`, prevent
  pXa/pXA from being persisted. **Receive-path enforcement** (PR #2888):
  `CheckCsEphemeralStateNode` in `add_case_status_tree` returns FAILURE if
  asserted PXA does not advance P from a pX state. See #2524, PR #2888.
- **CS history validity** (CSB-17-004, CSB-17-005): complete CS histories must
  be one of 70 valid histories; incomplete histories must be valid prefixes.
  Enforced in `add_case_status_tree` via `CheckCsHistoryPrefixNode` (precondition
  guard, rejects single-event PXA transitions that produce an invalid prefix).
  Multi-event advances and PXA regressions are deferred to
  `FilterCsPxaDimensionNode` (RSH-05). See #2524, PR #2888.
- **Ledger commit ordering** (from `specs/case-ledger-processing.yaml`
  CLP-10-006, ADR-0111): intake → precondition checks → ledger commit →
  protocol effects. Observable from audit replay.
- **CX in state `...px.`**: emitting CX must also trigger CS→P and emit CP.
  Observable: CX without CP from a sender in `...px.` is a detectable violation.
- **RS in EM Proposed = implicit EA**: VP-06-007 (SHALL). Observable: RS after
  EP without explicit EA is treated as acceptance by the sender.
