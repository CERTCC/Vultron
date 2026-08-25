---
source: CONCERN-1908
timestamp: '2026-08-25T00:00:00+00:00'
title: Blackboard key management has no structural enforcement, enabling a class of recurring runtime bugs
type: learning
---

Six distinct blackboard-related bugs appeared across May–July 2026, each
diagnosed and fixed in isolation. The root cause was consistent: blackboard
keys were untyped strings with no runtime enforcement of namespace, lifecycle,
or access permissions.

## Surface Symptom

Individual BT nodes failing at runtime with stale data, `KeyError`, or wrong
recipients because a blackboard key held an unexpected value. Evidence bugs
included: `BROADCAST-834` (stale `recipient_ids`), `BTND07-913` (partial write
in `memory=False` Sequence), `CC1-FLAKY` (global blackboard state ordering),
ISSUE-1716 (`KeyError` on unset READ key), ISSUE-1397 and CONCERN-1335
(namespaced key collision under concurrent BT execution).

## Underlying Problem

No typed key registry existed to enforce that (a) keys are namespaced per BT
instance, (b) a READ key that is registered but unset raises at access time
rather than returning `None` or raising unexpectedly, and (c) a WRITE key
written in one subtree is not readable by a sibling subtree in a different
context. Bugs were only catchable by integration tests.

## Resolution (2026-08-25)

By the time this concern was planned, the three suggested actions were
substantially complete:

1. **Typed Ports migration (#1809) — done.** All 219 BT DataLayer nodes in
   `vultron/core/behaviors/` migrated to `BehaviourWithPorts` /
   `DataLayerConditionWithPorts` / `DataLayerActionWithPorts`, replacing
   imperative `register_key()` with declarative `input_ports()` /
   `output_ports()`. Completed across PRs #1883–#1887 and cleanup #2530
   (2026-08-24). `NoDataAvailable` now raises at `initialise()` time on any
   missing required input, catching mis-wired nodes structurally.

2. **Architecture ratchet — in force.** `test/architecture/test_no_bare_register_key_datalayer_nodes.py`
   with `AUDITED_SITES = []` blocks any new bare `register_key()` DataLayer
   node from passing CI. Zero-tolerance since PR #1887.

3. **Collision/stale-read unit tests — substantially present**, with one
   narrow gap: the BROADCAST-834 no-op path class (BT-17-003 producer must
   clear output key on failure path) is specified and documented but has no
   dedicated back-to-back regression test in the broadcast sender domain.
   Tracked in #2577.

`CC1-FLAKY` (`test/bt/test_vultrabot.py`) remains deferred — it lives in
`vultron/bt/` (legacy simulation layer using a custom blackboard) which is
explicitly out of scope for this concern's resolution.

**Resolved**: 2026-08-25 — implementation tracked in #2577.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2579>.
