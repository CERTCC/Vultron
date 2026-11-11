---
source: CONCERN-3034
timestamp: '2026-11-11T14:53:40.419621+00:00'
title: A wrong-typed port value fails the whole tree
type: learning
---

Theme: theme:protocol-correctness — decides whether a mistyped blackboard port fails the node or the whole tree.

## Summary

Tightening a py_trees port from `data_type=object` to a concrete class changes
the failure mode for a wrong-typed blackboard value, and the change is larger
than it looks. This needs to be decided **once**, before any further tightening
sweep, because `_try_get_input()` is shared by ~150 nodes — the choice is not
per-port.

## The mechanism

`get_input()` raises `TypeError` on a type mismatch. `_try_get_input()`
(`vultron/core/behaviors/helpers.py`) catches only `NoDataAvailable` and
`NotImplementedError`, so the `TypeError` escapes `initialise()`.
`py_trees.behaviour.Behaviour.tick()` calls `initialise()` outside any
try/except, so the exception unwinds the tick and is absorbed by
`BTBridge.execute_tree`'s blanket `except Exception` — the **whole tree**
returns `BTExecutionResult(status=FAILURE)` with the type-mismatch message
logged.

Concretely: a node that previously ignored a junk value it never dereferenced
(e.g. `AdvanceOwnerRmToAcceptedNode` when `/case_id` was set) now takes its
enclosing Selector's fallback branch out of reach.

## Current state (deliberate, not accidental)

`_try_get_input()` was left alone in #2907 / #3011. A violated blackboard
contract is a wiring/programming error, not a protocol condition, so failing
closed and loudly is defensible — and it is already the behavior of the seven
ports hardened by #2909, so the alternative would mean changing those too.

## Why the obvious alternative is wrong

Catching `TypeError` in `_try_get_input()` and returning `None` would make a
corrupt value indistinguishable from an absent one. Several callers treat `None`
as "not supplied" and proceed, which is precisely the silent-degradation bug
ARCH-15 forbids ("Silent `None` Returns and Fake `SUCCESS` Are the Same Bug").
If the node-local `Status.FAILURE` shape is wanted instead, it has to be an
explicit failure signal, not a `None`.

## The unresolved tension

The project convention is that BT nodes return `FAILURE` rather than raise
(`notes/bt-pitfalls.md` § BT-HELPER-01), and an uncaught exception unwinding the
tick is a cruder instrument than a logged `FAILURE` with a feedback message. The
counter-argument is that a tree whose data contract is broken has no correct
partial outcome to report.

## Acceptance criteria

- [ ] AC-1: Decide whether a violated port `data_type` should fail the whole
      tree (status quo) or become an explicit node-local failure signal, and
      record the decision where a future sweep will find it (ADR-0044 amendment
      or a new ADR).
- [ ] AC-2: If the decision changes current behavior, apply it uniformly — the
      seven ports from #2909 and the seventeen from #2907/#3011 included.
- [ ] AC-3: Reconcile the decision with `notes/bt-pitfalls.md` § BT-HELPER-01 so
      the two do not read as contradictory.

## Source

Surfaced by PR #3018 (issues #2907 / #3011). Analysis was captured in
`plan/incoming/learnings/20260901-2907-port-type-error-fails-whole-tree.md`;
filed here so it is tracked rather than waiting on a `learn` cycle.


**Resolved**: 2026-11-11 — no implementation issues; the decision (keep whole-tree failure), its spec rule BTND-03-021, the `_try_get_input()` dedupe and the pinning test all land in the docs PR.
Docs PR: https://github.com/CERTCC/Vultron/pull/6276.
Spec: `specs/behavior-tree-node-design.yaml`.
Notes: `notes/bt-pitfalls.md`.
