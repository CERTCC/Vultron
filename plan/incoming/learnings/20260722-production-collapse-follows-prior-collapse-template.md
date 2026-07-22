---
title: Production BT collapse issues (FUZZ-08x) should reuse the prior collapse as a concrete template
type: learning
timestamp: 2026-07-22T00:00:00Z
source: ISSUE-1310
---

## Observation

Issue #1310 (Production Collapse 2 — publication-intent per-artifact arms) was
almost a structural clone of the already-merged Production Collapse 1
(issue #1309 / PR #1566, in `acquire_exploit_strategy_tree.py`). Both collapses:

- Replace N granular simulator nodes with a single **Evaluator** that writes a
  typed Pydantic decision record to the blackboard.
- Keep the decision model **in the core tree module**
  (`vultron/core/behaviors/report/*_tree.py`), and have the demo fuzzer
  Evaluator import that model at module level — so the tree module's factory
  helpers use **deferred (function-local) imports** of the fuzzer to avoid the
  circular dependency.
- Leave the eliminated ProtocolInternal/bypass fuzzer classes in place in the
  demo module as catalogued simulator stand-ins; they simply stop being wired
  into the production tree.
- Update the ADR (proposed → accepted), remove the `PROVISIONAL` marker from
  the BT-20-xxx spec entry (BT-21-002), and rewrite the matching
  `notes/bt-fuzzer-nodes-report-management.md` § "Production Collapse N"
  section plus each affected node's "Factory-fn placement" line.

## How to apply

When building a FUZZ-08x Production Collapse issue, read the most recently
merged sibling collapse first and mirror its file layout, import structure,
test file shape, and doc-update checklist. The `EvaluatorCallOutPoint` mixin
writes `typ()` (a default-constructed instance) on SUCCESS, so a decision
model's field **defaults must encode the sensible default outcome** (e.g.
`PublicationIntentDecision` defaults to publish fix+report, withhold exploit).

For arm gating, use `Selector(Sequence(ShouldPublishX, Prepare, Publish),
Inverter(ShouldPublishX))` — the positively-named gate (BTND-08-001) plus an
`Inverter` skip branch. This makes a not-intended arm a graceful SUCCESS no-op
while still propagating a genuine Prepare/Publish FAILURE (the Inverter only
fires SUCCESS on the not-intended path). This is the same routing-no-op idiom
used in `vultron/core/behaviors/sync/announce_tree.py`.

See [[20260720-git-rebase-duplicate-pick-on-large-branch]] — the single-commit
70+-file branch again hit the rebase duplicate-pick sequencer bug during
create-pr; the cherry-pick-onto-fresh-branch workaround resolved it.

**Promoted**: 2026-07-22 — captured in `notes/bt-integration.md`.
Docs PR: TBD (fill in after PR is opened).
