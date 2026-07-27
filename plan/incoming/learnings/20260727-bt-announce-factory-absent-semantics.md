---
title: "BT-14-001 vs. receive-side no-factory: best-effort semantics for SendAnnounceEmbargoEventNode"
type: learning
timestamp: "2026-07-27"
source: ISSUE-1687
signal: design-question
---

## Decision

`SendAnnounceEmbargoEventNode.update()` returns `SUCCESS + WARNING` (best-effort)
when `trigger_activity_factory` is `None` OR when no Case Manager participant
is found — rather than `FAILURE` as BT-14-001 (broadcast nodes) would suggest.

## Why

`RemoveEmbargoEventFromCaseReceivedUseCase` calls `BTBridge(datalayer=self._dl)`
without a `trigger_activity` factory — the receive-side path intentionally omits
it. With `FAILURE` semantics inside a `memory=False` Sequence inside a Selector,
the Selector falls through to `EmbargoWasNotActive` (always SUCCESS) *after*
`ApplyEmbargoTeardownNode` has already written `EM=EXITED` to the DataLayer.
The Sequence would appear to "not have been active" despite state being mutated —
confusing and hard to detect.

Best-effort semantics (`SUCCESS + WARNING`) are the right call here:
teardown must not be blocked by notification gaps. The missing-factory case is an
operational deployment gap (receive-side use cases don't wire factories), not a
data error.

## Spec tension

BT-14-001 says broadcast nodes should return FAILURE when the factory is
unavailable. The `AutoCloseBranch` pattern (used elsewhere in the codebase) uses
the same best-effort override. This is a recurring pattern: when a node sits
inside a Selector with a fallback Success child *and* precedes a state mutation
that has already fired, FAILURE semantics break the invariant that Selector
"not active" branch means "nothing happened." A spec note or ADR clarifying
when BT-14-001 best-effort override is appropriate would prevent this from being
re-litigated in future nodes.
