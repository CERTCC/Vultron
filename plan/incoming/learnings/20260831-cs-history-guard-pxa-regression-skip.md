---
title: "History-prefix guard must skip PXA regressions to avoid false FAILURE"
type: learning
timestamp: "2026-08-31T00:00:00Z"
source: ISSUE-2524
signal: design-question
---

`CheckCsHistoryPrefixNode` calls `cs_transition_event(current_cs, asserted_cs)`
to find the single event between states. For a PXA regression (e.g., current=Pxa,
asserted=pxa), `cs_transition_event` still returns an event — but in the backward
direction (e.g., `CSEvent.P` for `Pxa→pxa`). `is_valid_cs_history_prefix([P],
start=VFDPxa)` then fails because P is not valid from a state where P is already
true.

Without the pre-check, valid EM-advance + PXA-regression payloads (e.g.,
`test_valid_em_advance_with_pxa_regression_applies_em_and_refuses_pxa`) caused
false FAILURE from the history-prefix guard before reaching
`FilterCsPxaDimensionNode`.

**Fix**: early return `Status.SUCCESS` from `CheckCsHistoryPrefixNode.update()`
when `is_monotonic_pxa_forward(current_pxa, asserted_pxa)` is False. PXA
regressions are a monotone-filter concern, not a history-prefix concern.

**Location**: `vultron/core/behaviors/status/nodes/cs_invariant_guards.py`,
`CheckCsHistoryPrefixNode.update()`.
