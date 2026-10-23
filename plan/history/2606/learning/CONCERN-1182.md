---
source: CONCERN-1182
timestamp: '2026-06-25T20:15:41.108835+00:00'
title: FUZZ-08a missed factory-fn placement mapping step
type: learning
---

## Summary

The FUZZ-08a implementation (PR #1179, based on #1150) cataloged fuzzer nodes
and mapped them from old `vultron/bt/` classes to new py_trees node classes —
but it stopped there. The missing step is mapping *where in the current
use-case BT factory functions* each fuzzer node should be inserted to achieve
simulator parity. Without this placement map, the call-out point abstraction
work in #1151 lacks the information it needs to design the correct seams.

## Category

Implementation Gap

## Severity

Medium

## Evidence

PR #1179 updated fuzzer node cross-references and class mappings but no
factory functions in `vultron/core/behaviors/` were modified. The old BT
simulator placed fuzzer nodes at specific positions in BT subtrees; those
positions need to be traced to their equivalents in the current (more complex)
factory functions. The use cases have evolved into more complex behavior trees
than the simulator had, but their overall structure remains approximately the
same.

## Impact if Ignored

Fuzzer parity (epic #427) and the call-out abstraction (#1151) will proceed
without a validated placement map, risking incorrect or incomplete seam
locations that require rework. #1151 cannot be properly designed without
knowing where the seams belong.

## Suggested Action

For each fuzzer node cataloged in FUZZ-08a, trace its original position in the
old BT simulator and identify the corresponding location(s) in the current
factory functions. Likely requires a mix of agent review and human judgment for
ambiguous cases. Produce a placement map before or alongside #1151 work.

**Resolved**: 2026-06-25 — implementation tracked in #1187.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1186>.
Spec: n/a. Notes: `notes/bt-fuzzer-nodes.md` (updated).
