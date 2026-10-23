---
source: ISSUE-1173
timestamp: '2026-07-10T20:08:10.729359+00:00'
title: 'FUZZ-08d: Apply EvaluatorCallOutPoint to all Evaluator-shaped fuzzer nodes'
type: implementation
---

## Issue #1173 — FUZZ-08d: Implement all Evaluator-shaped call-out points (cross-domain)

Applied EvaluatorCallOutPoint (and RetrieverCallOutPoint where appropriate) to 25 Evaluator-shaped fuzzer nodes across all domains: embargo (10 nodes), prioritize (1 Evaluator + 1 Retriever), assign_vul_id (2), deploy_fix (4), acquire_exploit (2), report_to_others (4), close_report (1), publication (4).

Each node: EvaluatorCallOutPoint as first parent (MRO), output_keys dict with_verdict-suffixed key, blackboard contract docstring (BT-18-001).

Test fixes: added node.setup() before node.update() in 5 legacy test files (test/fuzzer/) since the mixin now requires setup() to register the blackboard client.

PR: <https://github.com/CERTCC/Vultron/pull/1351>
