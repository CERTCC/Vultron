---
source: CONCERN-1677
timestamp: '2026-07-27T17:55:33.442654+00:00'
title: 'Case-actor close-ready condition: AutoCloseBranchNode is a god node'
type: learning
---

## Summary

Case-actor should autonomously decide to emit `close_case` once all participants
have reached RM=CLOSED. Currently the demo puppeteer performs this check
externally (`wait_for_all_participants_rm_closed`) and then instructs each
participant to close the case via trigger endpoints. There is no BT-level
condition node that case-actor evaluates to determine readiness for closure.

## Category

Protocol / BT behavior gap

## Severity

Medium — correct behavior occurs in the demo but only because the script
enforces the right ordering. A real deployment would have no such guarantee.

## Evidence

`vultron/demo/scenario/fv_demo.py` `_phase_case_closure()`: each actor is told
to close via `actor_closes_case()` calls followed by
`wait_for_all_participants_rm_closed()`. The wait is a postcondition check in the
demo, not a precondition evaluated by case-actor's BT.

No BT node named `CloseReadyConditionNode` or equivalent exists in
`vultron/core/behaviors/`.

## Impact if Ignored

Case-actor can emit `close_case` before all participants have agreed, violating
the protocol invariant that case closure requires consensus. In a real
multi-party deployment this could close a case while participants still have
open work.

## Suggested Action

Design and implement a `CloseReadyConditionNode` (or equivalent guard) in the
case-actor BT that checks all known participants are at RM=CLOSED before the
`close_case` emit is reached. The demo script's external wait can then serve as
a test oracle rather than a control mechanism.

## Resolution

2026-07-27 — `AutoCloseBranchNode` in
`vultron/core/behaviors/status/nodes/lifecycle.py` already implements the
all-participants-RM-CLOSED check and emits `close_case` autonomously. However,
the check and emit logic is buried inside `update()` (god-node pattern,
BT-IDM-03 violation). The concern was partially addressed but the BT structure
violation remains.

Implementation tracked in #1716 (decompose `AutoCloseBranchNode` into
`AllParticipantsRMClosedConditionNode` + `CloseNotYetEmittedConditionNode` +
routing guard + emit node as a proper BT Sequence, per DEMOMA-07-006).

Docs PR: <https://github.com/CERTCC/Vultron/pull/1715>.
Spec: `specs/multi-actor-demo.yaml` DEMOMA-07-006.
Notes: `vultron/core/behaviors/AGENTS.md`.
