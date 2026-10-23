---
source: CONCERN-1069
timestamp: '2026-06-22T14:43:24.614266+00:00'
title: 'Single-BT ratchet gap: multi-execute_with_setup detection'
type: learning
---

## Summary

`test/architecture/test_single_bt_execution_received_side.py` enforces the
single-BT-per-inbox-delivery invariant (CLP-10-005 / ADR-0022) via a proxy
metric: direct imports of `create_guarded_commit_case_ledger_entry_tree` in
`use_cases/` files. After #1052 (PR #1066), `KNOWN_VIOLATIONS` is empty and
the proxy shows zero violations.

One specific gap remains undetected: nothing prevents a new or refactored use
case from calling `execute_with_setup()` more than once inside a single
`execute()` method — a violation of the same invariant that would be invisible
to the current proxy ratchet.

## Required Work

Add an AST-based invariant test (not a ratchet with KNOWN_VIOLATIONS, but a
hard assertion) that walks each `.py` file under `vultron/core/use_cases/`,
finds each `execute()` method body, counts `execute_with_setup` call sites,
and asserts ≤ 1 per method. The baseline is already clean (zero violations),
so the test ships as an unconditional assertion — no escape hatch.

## References

- Spec: `specs/case-ledger-processing.yaml` CLP-10-005
- ADR: `docs/adr/0022-single-bt-execution-for-received-side-case-actor-routing.md`
- Parent ratchet: `test/architecture/test_single_bt_execution_received_side.py`

**Resolved**: 2026-06-22 — implementation tracked in #1074.
