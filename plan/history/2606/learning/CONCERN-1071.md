---
source: CONCERN-1071
timestamp: '2026-06-22T14:46:41.557126+00:00'
title: 'Single-BT ratchet gap: direct DataLayer mutations in execute()'
type: learning
---

## Summary

The single-BT ratchet (CLP-10-005 / ADR-0022) enforces that received-side
`execute()` methods delegate all domain work to a single BT via
`execute_with_setup()`. The proxy metric (guarded-commit factory import) is
clean after #1066. But a broader violation class remains undetected: direct
DataLayer mutations (`dl.save`, `dl.create`, `dl.update`, `dl.delete`) called
directly inside `execute()` rather than inside a BT leaf node.

These direct mutations bypass the BT audit trail, skip the hash-chained
ledger-commit path, and constitute protocol-significant behavior outside the
tree — the exact anti-pattern BT-06-001 and BT-15-001 prohibit.

## Known violations (post-#1066 baseline)

| File | Method | Mutation |
|---|---|---|
| `received/case_participant.py` | `execute()` (×2) | `self._dl.save(case)` |
| `received/actor/ownership.py` | `execute()` | `self._dl.save(case)` |
| `received/actor/announce.py` | `execute()` | `self._dl.save(case_obj)` |
| `received/unknown.py` | `execute()` | `self._dl.save(record)` |

(`received/case/create.py` was clean at audit time — already migrated.)

## References

- Spec: `specs/case-ledger-processing.yaml` CLP-10-005, BT-06-001, BT-15-001
- ADR: `docs/adr/0022-single-bt-execution-for-received-side-case-actor-routing.md`

**Resolved**: 2026-06-22 — implementation tracked in #1076 (ratchet test)
and #1077 (migration of 4 files), both blocked by #1069.
Docs PR: [#1075](https://github.com/CERTCC/Vultron/pull/1075).
