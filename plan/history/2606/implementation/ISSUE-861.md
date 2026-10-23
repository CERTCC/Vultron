---
source: ISSUE-861
timestamp: '2026-06-22T18:52:20.228922+00:00'
title: 'FUZZ-02: Port embargo management fuzzer nodes'
type: implementation
---

## Issue #861 — FUZZ-02: Port embargo management fuzzer nodes to vultron/demo/fuzzer/embargo.py

Ported all 15 embargo management fuzzer nodes from
`vultron/bt/embargo_management/fuzzer.py` to the new
`vultron/demo/fuzzer/embargo.py` module using the py_trees probabilistic
base types from FUZZ-01 (#860).

Each node subclasses the appropriate `WeightedBehavior` subclass
(`ProbablyFail`, `UsuallyFail`, `AlwaysSucceed`, etc.) and carries a
docstring covering semantic function, input category, success
probability, and automation potential per BT-16-003 and BT-16-005.

`AvoidEmbargoCounterProposal` is implemented as `UsuallySucceed`
(p=0.75), the logical complement of `WillingToCounterEmbargoProposal`
(p=0.25).

Added 179 unit tests in `test/fuzzer/test_embargo.py` (placed under
`test/fuzzer/` rather than `test/demo/fuzzer/` to avoid the
auto-integration marker from `test/demo/conftest.py`). All 15 nodes are
re-exported from `vultron/demo/fuzzer/__init__.py`.

Full suite: 3950 passed, 37 skipped, 5 xfailed. All linters clean.

PR: [#1106](https://github.com/CERTCC/Vultron/pull/1106)
