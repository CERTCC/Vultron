---
title: Sentinel blackboard writes on BT FAILURE enable Selector fallback without re-running the failing node
type: learning
timestamp: 2026-07-31T00:00:00Z
source: ISSUE-1873-sentinel-bboard
signal: design-question
---

When a py_trees Sequence needs a fallback action on node failure, the standard Selector pattern works only if the failing node leaves the blackboard in a usable state.  In `ReconstructChainTailNode`, the normal SUCCESS path writes `tail_hash` and `tail_index`; on `VultronValidationError` the node previously returned FAILURE with those keys unset.

The fix writes sentinel values (`tail_hash=""`, `tail_index=-1`) **before** returning FAILURE so the sibling `SendRejectLogEntryNode` in the `ReconstructOrRejectOnMissingCase` Selector can read them and send a well-formed Reject with `last_accepted_hash=""`.

This is a reusable idiom for any BT node that needs to signal structured failure context downstream: write into the blackboard before returning FAILURE, then wrap in a Selector whose fallback consumes those values.  The pattern is only safe when the sentinel values are semantically distinct from valid data (empty string vs a 64-char hex hash; -1 vs a non-negative index) so consumers can detect the error state if needed.

**Promoted**: 2026-08-17 — captured in notes/bt-pitfalls.md (Sentinel Blackboard Writes section).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>.
