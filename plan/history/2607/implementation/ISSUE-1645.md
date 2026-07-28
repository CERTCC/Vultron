---
source: ISSUE-1645
timestamp: '2026-07-23T21:23:42.704951+00:00'
title: Implement call-out point backend bundles and three-mode selection
type: implementation
---

## Issue #1645 — FUZZ-08c-impl: Implement call-out point backend bundles and three-mode selection

Implemented the call-out point backend bundle system (BT-23) designed in issue #1631.

Key deliverables:

- Promoted `CallOutBackendFactory` to a `@runtime_checkable Protocol` (BT-23-004)
- Created 9 domain `frozen @dataclass` bundle classes in `vultron/demo/fuzzer/bundles/`
- Shipped `<DOMAIN>_DETERMINISTIC` (ceiling/floor rule) and `<DOMAIN>_STOCHASTIC` singletons per domain
- Rewired all 11 tree builders to accept `call_out: <Domain>Bundle | None = None`; lazy import defaults to DETERMINISTIC singleton (preserves BT-16-001 hexagonal architecture constraint)
- Re-exports all 9 classes and 18 singletons from `bundles/__init__.py`
- Updated 13 existing test files; added 2 new test files (430+ lines)
- 6262 tests pass, 0 failures

PR: <https://github.com/CERTCC/Vultron/pull/1658>
