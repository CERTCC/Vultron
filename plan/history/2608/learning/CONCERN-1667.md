---
source: CONCERN-1667
timestamp: '2026-08-11T14:59:53.464454+00:00'
title: 'CaseStatus authority model: outbound emit invariant designed'
type: learning
---

## Outcome

CONCERN-1667 ("CaseStatus authority model is undesigned") is resolved at the
design level. The two-seam inbound authorization model (ADR-0046 / IDEA-1836)
was already fully implemented. The remaining gap — the outbound emit invariant
— is now fully specified and planned.

## Key decisions

1. **CaseStatus is the only protocol channel for EM/PXA state changes.**
   Every CaseActor-side EM or PXA mutation MUST be followed by a canonical
   `CaseStatus` ledger write (RSH-04-002, RSH-04-003).

2. **Only the CaseActor (CASE_MANAGER) emits `Add(CaseStatus)` directly.**
   All other participants embed a suggested CaseStatus inside
   `Add(ParticipantStatus)` and let the two-seam model decide adoption
   (RSH-04-001).

3. **DRY: one shared node, not N inline patches.**
   `EmitCaseStatusUpdateNode` (new BT node in
   `vultron/core/behaviors/status/nodes/case_status.py`) will be wired after
   each of the 6 EM lifecycle nodes. Direct ledger write — no inbox loopback.

4. **`EmitAddCaseStatusToSelfNode` is a recognized kludge.**
   Its inbox-loopback pattern inverts causality. Refactoring it out is a
   follow-on issue blocked-by the main impl.

## Causal ordering invariant

```text
CaseActor mutates EM/PXA state
  → writes CaseStatus to canonical ledger (authoritative)
  → Announce(CaseLedgerEntry) syncs participants
```

NOT the inbox-loopback pattern:

```text
[kludge] EmitAddCaseStatusToSelf → inbox → add_case_status_tree → writes ledger
```

## Docs produced

- `specs/received-status-handling.yaml`: RSH-04 group added (RSH-04-001–004)
- `notes/received-status-authorization.md`: § "CaseStatus Emission Authority"
- `docs/adr/0046-received-status-authorization.md`: Outbound Emit Invariant section

## Implementation issues spawned

- #2175 (size:M): implement `EmitCaseStatusUpdateNode`; wire after all 6 EM
  lifecycle BT nodes; satisfies RSH-04-002 through RSH-04-004
- #2176 (size:S): refactor `EmitAddCaseStatusToSelfNode` to direct ledger
  write; blocked-by #2175

## Reference

Docs PR: <https://github.com/CERTCC/Vultron/pull/2174>
Parent epic: #1935
