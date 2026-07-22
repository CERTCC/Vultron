---
source: ISSUE-1565
timestamp: '2026-07-22T15:38:50.839725+00:00'
title: BT-18-001 blackboard write contract tests
type: implementation
---

## Issue #1565 — BT-18-001 blackboard write contract integration tests

Added behavior-contract integration tests for all four acquire_exploit call-out points with non-empty output_keys.

### Changes

- `test_acquire_exploit_strategy_tree.py`: added `clear_blackboard` autouse fixture; `test_evaluate_exploit_strategy_writes_blackboard_on_success` (ticks AcquireExploitStrategyBT Selector with always-fail HaveExploit stub, asserts ExploitStrategyDecision on blackboard); `test_have_exploit_success_skips_evaluator_no_write` (Selector short-circuit, no key written).
- `test_call_out_point.py`: parametrized `test_acquire_exploit_node_writes_blackboard_on_success` covering EvaluateExploitPriority, _DeterministicDevelopExploit,_DeterministicPurchaseExploit; deterministic subclasses inherit production output_keys.

### Deferred

- #1594: behavior-contract test for PrioritizePublicationIntents (Collapse 2 parity).

PR: <https://github.com/CERTCC/Vultron/pull/1596>
