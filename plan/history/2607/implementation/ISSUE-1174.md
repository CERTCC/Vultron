---
source: ISSUE-1174
timestamp: '2026-07-13T17:22:43.959491+00:00'
title: Apply RetrieverCallOutPoint to all Retriever-shaped fuzzer nodes
type: implementation
---

## Issue #1174 — FUZZ-08e: Implement all Retriever-shaped call-out points

Applied RetrieverCallOutPoint mixin to 14 Retriever-shaped fuzzer nodes across 6 files. 9 binary Retrievers (empty output_keys, per BT-18-006), 5 data-producing Retrievers (with distinct str-typed output keys). All nodes have BT-18-001 blackboard contract docstring sections. Added 51 new test assertions. Fixed one pre-existing test (test_seeded_determinism needed node.setup() before update() once RequestId gained output_keys). PR: <https://github.com/CERTCC/Vultron/pull/1368>
