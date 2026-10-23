---
source: ISSUE-1151
timestamp: '2026-07-08T17:35:13.879423+00:00'
title: 'FUZZ-08b: Call-out point abstraction layer (ADR-0025)'
type: implementation
---

## Issue #1151 — FUZZ-08b: Call-out point abstraction layer

Implemented the full call-out point abstraction layer (ADR-0025):

- `CallOutBackendFactory` type alias in `vultron/core/behaviors/call_out_point.py`
- Five shape mixin classes in `vultron/demo/fuzzer/call_out_point.py` (Evaluator, Retriever, Composer, Actuator, Sentinel)
- Illustrative `NewValidationInfoSentinel` subclass (full impl: #1175)
- Factory injection into `create_validate_report_tree`, `create_prioritize_subtree`, and new `create_publication_tree`
- BT-18-001 blackboard contract docstrings on all exemplar nodes
- ADR-0025 advanced from proposed to accepted
- 44 new tests; 20 integration tests made deterministic with `_always_succeed_factory`

PR: <https://github.com/CERTCC/Vultron/pull/1267>
