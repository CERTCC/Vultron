---
title: "BehavioralSpec group trigger vs precondition mismatch is a recurring risk"
type: learning
timestamp: 2026-07-15T00:00:00Z
source: ISSUE-1424
---

When writing BehavioralSpec items in a group with a `state_entered` trigger,
the precondition `rm_state` (or `em_state`) must list the state that was just
*entered*, not the state before the transition. Code review caught `RMB-11-002`
with `rm_state: [RECEIVED]` inside the `state_entered: RM.INVALID` group — an
impossible precondition.

Pattern: for any `state_entered: RM.X` group, every item's `rm_state`
precondition must include `X`, not a predecessor state.

Also: when a message-receive group covers "all states", add an explicit
START-state variant per VP-03-010 (RE+GI+RK). The review found `RMB-07` and
`RMB-08` missing their START-state items while `RMB-02` through `RMB-06`
each had one. The pattern should be systematically applied across all R*
message groups.

**Promoted**: 2026-07-15 — captured in notes/behavioral-conformance-specs.md.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1458>8>8>8>8>.
