---
source: CONCERN-5584
timestamp: '2026-11-16T20:26:23.091603+00:00'
title: Nothing unregisters a py_trees blackboard client
type: learning
---

Theme: theme:test-and-ci — a process-global registry that only grows, so a seeded id source collides and a long-running container leaks.

## Summary

`py_trees.blackboard.Blackboard.clients` is process-global and nothing ever calls
`Client.unregister()`. Three clients are registered per inbox delivery and never
released:

- `vultron/core/behaviors/bridge.py:331` — one `Client` per `setup_tree`
- `vultron/core/behaviors/inbox/_process_payload.py:91` — `InboxOrchestrator-setup`
- `vultron/core/behaviors/inbox/_process_payload.py:135` — `InboxOrchestrator-result`

`py_trees` offers `Client.unregister(clear=True)` and has no `__del__` cleanup, so
the registry grows monotonically for the life of the process.

Two consequences, of very different weight:

1. **Slow growth in a server.** An actor container's registry gains three entries
   per delivery. Prototype-proportionate: unbounded but small, and no correctness
   effect while ids are random.
2. **An id collision when `uuid4` is seeded.** The demo recorder seeds `uuid4`
   through `deterministic_run`, so a second run in one process redraws the first
   run's client ids and `Client.__init__` raises "this unique identifier has
   already been registered". `vultron/demo/determinism.py`'s `reset_blackboard()`
   works around this by clearing the whole blackboard between runs (#5532), which
   mops up at the recorder's level rather than at the source.

## Why this is separate from #5572

#5572 covers the autouse test fixture in `test/conftest.py`, which clears
`Blackboard.storage` but not the client registry. That is the test-isolation half
of the same omission. This issue is the half inside `vultron/core/behaviors/`: the
code that creates the clients never releases them, in tests and in a server alike.
Fixing this one would make both workarounds unnecessary.

## Fix or approach

Release each client where it is created — unregister it in `execute_with_setup`'s
cleanup and around the two `_process_payload` clients — or hold one `Client` per
bridge instance instead of one per `setup_tree`. Then re-check whether
`reset_blackboard()`'s client-registry clear and #5572's fixture widening are still
needed.

## Reference

Found by the review of PR #5568 (issue #5532, the fixed demo cast). Related: #5572.

---

**Resolved**: 2026-11-16 — implementation tracked in #6550, #6551, #6552, #6553, #6554, under Epic #6549; follow-up Concern #6555. #6554 also absorbs #5572.

The planning found the seeded-id collision already gone (the recorder seeds Vultron's own id source, not `uuid.uuid4`), and the growth larger than reported: one client per node that attaches one, about 7 to 10 per delivery. Releasing at the end of a run cannot reach subtrees that nodes run through nested bridge calls (about 25 sites), so the fix makes every act one fixed-shape tree first.

Docs PR: https://github.com/CERTCC/Vultron/pull/6548.
ADR: `docs/adr/0207-a-tree-has-a-fixed-shape-and-every-act-runs-one.md`.
Spec: `specs/behavior-tree-integration.yaml` (BT-25).
Notes: `notes/bt-integration.md` § "One Fixed-Shape Tree per Act".
