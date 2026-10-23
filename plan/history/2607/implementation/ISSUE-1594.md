---
source: ISSUE-1594
timestamp: '2026-07-22T16:01:07.590164+00:00'
title: BT-18-001 behavior-contract test for default PrioritizePublicationIntents
type: implementation
---

## Issue #1594 — BT-18-001 follow-up: behavior contract test for PrioritizePublicationIntents in publication tree

PR: <https://github.com/CERTCC/Vultron/pull/1597>

Closed a coverage gap identified during review of the #1565 blackboard-contract
work: no test exercised the **real default** `PrioritizePublicationIntents`
Evaluator's blackboard-write contract — all prior tick/gating tests either
stubbed the Evaluator or wrote the intent record manually.

Added `test_full_tick_with_default_evaluator_writes_intent_record` to
`test/core/behaviors/report/test_publication_tree.py`. It builds
`create_publication_tree()` with the default `PrioritizePublicationIntents`
factory (deterministic `AlwaysSucceed`), replacing only the probabilistic
`Prepare*`/`Publish` arm call-out points with deterministic marker stubs so the
full tree ticks to `SUCCESS` on every run, then asserts
`/publication_intent_decision` holds a `PublicationIntentDecision` instance
(BT-18-001). Mirrors the `*_writes_blackboard_on_success` pattern in
`test/demo/fuzzer/test_call_out_point.py`.

Test-only change (49 insertions, size:S). Both ACs satisfied. Full suite:
5303 passed, 39 skipped, 2 pre-existing xfails. All four linters clean.
