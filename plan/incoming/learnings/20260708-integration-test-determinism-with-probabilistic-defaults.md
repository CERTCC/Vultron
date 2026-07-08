---
title: "Integration tests must use deterministic factories when BT default is probabilistic"
type: learning
timestamp: 2026-07-08
source: ISSUE-1151
---

When a tree builder's default factory produces a `WeightedBehavior` node
(e.g., `AlmostAlwaysSucceed` at 90% success rate), integration tests that
assert `result.status == Status.SUCCESS` become flaky.  Two such nodes in
series give ~81% tree success — a failure probability that surfaces within
a few test runs.

**Pattern that caused this**: Adding factory injection to
`create_validate_report_tree` where the fuzzer defaults (`EvaluateReportCredibility`,
`EvaluateReportValidity`) are `AlmostAlwaysSucceed` nodes.  Existing integration
tests called the tree builder with no factory args and asserted SUCCESS.

**Fix**: Add a module-level `_always_succeed_factory` helper to the test
file and pass it explicitly to all integration tests that require SUCCESS.
Tree-structure tests (node names, child counts) and FAILURE-path tests
(missing DataLayer, missing report) don't need it.

```python
def _always_succeed_factory(name: str) -> py_trees.behaviour.Behaviour:
    class _AlwaysSucceed(py_trees.behaviour.Behaviour):
        def update(self):
            return py_trees.common.Status.SUCCESS
    return _AlwaysSucceed(name)
```

**Rule**: Any time a tree builder's default factory wraps a probabilistic
fuzzer node, update all integration tests that assert SUCCESS to pass an
explicit deterministic factory.  Tests that check tree structure (names,
children) or FAILURE paths are unaffected.

**Promoted**: 2026-07-08 — captured in `notes/bt-integration.md`
§ "Integration Tests Must Use Deterministic Factories When BT Default Is
Probabilistic", `test/AGENTS.md` § "BT Factory Determinism", and root
`AGENTS.md` pitfall entry.
Docs PR: (TBD — filled in after PR is opened)
