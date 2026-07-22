---
title: Full-tree tick tests must stub only the probabilistic call-out points, not the deterministic Evaluator under test
type: learning
timestamp: 2026-07-22T00:00:00Z
source: ISSUE-1594
---

## Observation

To write a behavior-contract test that ticks `create_publication_tree()` to
SUCCESS and verifies the **default** `PrioritizePublicationIntents` Evaluator's
blackboard write, you have to reckon with a determinism split among the
collapsed publication tree's call-out points:

- `PrioritizePublicationIntents` is `EvaluatorCallOutPoint + AlwaysSucceed`
  (`success_rate = 1.0`) — deterministic, and the node whose contract is under
  test. It must be left at its **default** factory, or the test proves nothing.
- The arm nodes `PrepareExploit` / `PrepareFix` / `PrepareReport` (`AlmostAlways
  Succeed`, 0.90) and `Publish` (`AlmostAlwaysSucceed`, 0.90) are
  **probabilistic**. Left at default they make the full-tree tick flaky.

So the correct recipe is: keep `prioritize_publication_intents_factory` at its
default, and inject deterministic marker-factory stubs for **only** the
`prepare_*_factory` and `publish_factory` params. The existing `_marker_factory`
helper in `test_publication_tree.py` already returns an unconditional-SUCCESS
stub for exactly this. Add an `isinstance(tree.children[0],
PrioritizePublicationIntents)` guard so a future refactor that accidentally
stubs the Evaluator fails loudly rather than silently gutting the test.

With the default `PublicationIntentDecision` (publish fix + report, withhold
exploit) the exploit arm is a graceful `Inverter` no-op while the fix/report
arms run their stubs — so the root `Sequence` reaches SUCCESS.

The blackboard storage key carries a leading slash (`/publication_intent_
decision`); assert against `py_trees.blackboard.Blackboard.storage`, and rely on
the file's `autouse` `clear_blackboard` fixture to keep the assertion
non-vacuous.

## Stale-issue-body note

Issue #1594's body referenced a `_FixedIntents` stub "in all existing tick
tests" — that symbol no longer exists in `test_publication_tree.py` (the arm
tests now write the record directly via `_write_intent`). The *intent* of the
AC was still correct and current; verify the described test-file state in code
before mirroring a pattern named in an issue body. See
[[20260721-issue-1484-already-implemented]] for the general "verify issue claims
against current code first" pattern.

## Pattern to apply

When ticking a collapsed FUZZ-08x tree to SUCCESS to test one call-out point's
contract, check each leaf's fuzzer base type: leave the node-under-test at its
default factory, and inject deterministic stubs for every *other* probabilistic
call-out point in the tick path. Never stub the node whose contract you are
asserting.

**Promoted**: 2026-07-22 — captured in `test/AGENTS.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1608>8>8>.
