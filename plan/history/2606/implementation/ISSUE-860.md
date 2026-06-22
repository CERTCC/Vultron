---
source: ISSUE-860
timestamp: '2026-06-22T18:23:15.285066+00:00'
title: Port probabilistic base node types to vultron/demo/fuzzer/
type: implementation
---

## Issue #860 — FUZZ-01: Port probabilistic base node types to vultron/demo/fuzzer/base.py (py_trees)

Ported the probabilistic base classes from `vultron/bt/base/fuzzer.py` to a
new `vultron/demo/fuzzer/base.py` module using `py_trees.behaviour.Behaviour`
as the base class. This is the foundational FUZZ-01 issue that unblocks
FUZZ-02 through FUZZ-07.

**Delivered**:

- `vultron/demo/fuzzer/base.py`: `WeightedBehavior` base class, 14 named
  probability subclasses, `AlwaysSucceed`, `AlwaysFail`, `SuccessOrRunning`,
  and 6 aliases (`LikelyFail`, `RarelySucceed`, `LikelySucceed`,
  `RandomSucceedFail`, `RandomConditionNode`, `RandomActionNode`)
- `vultron/demo/fuzzer/__init__.py`: re-exports all 24 public names (AC-3)
- `test/fuzzer/test_base.py`: 73 unit tests covering success_rate attributes,
  empirical distributions (±3%), aliases, and package re-exports (AC-4)
- Tests placed in `test/fuzzer/` (not `test/demo/fuzzer/`) to avoid the
  `test/demo/` conftest auto-marking them as `integration`

All linters (Black, flake8, mypy, pyright) clean. 3469 unit tests pass.

PR: [#1105](https://github.com/CERTCC/Vultron/pull/1105)
