---
source: ISSUE-1309
timestamp: '2026-07-21T17:25:36.818033+00:00'
title: FUZZ-08a — EvaluateExploitStrategy collapsed subtree (Production Collapse 1)
type: implementation
---

## Issue #1309 — FUZZ-08a: EvaluateExploitStrategy collapsed subtree

Implemented ADR-0027 / BT-20-001 Production Collapse 1: replaced five simulator BT nodes with two independently-swappable call-out points (HaveExploit Retriever + EvaluateExploitStrategy Evaluator). Added ExploitStrategyDecision Pydantic model, create_acquire_exploit_strategy_tree() factory with ADR-0025 call-out pattern, 15 new tests, and advanced ADR-0027 to accepted. IMPROVE fix: output_keys type corrected from str to ExploitStrategyDecision. DEFER: blackboard integration tests tracked in #1565.

PR: <https://github.com/CERTCC/Vultron/pull/1566>
