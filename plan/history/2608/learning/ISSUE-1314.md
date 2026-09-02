---
title: Code review of PR for #1314 surfaced 5 pre-existing bugs in unrelated files
type: learning
timestamp: "2026-08-27T00:00:00Z"
source: ISSUE-1314
signal: concern
---

During the code review for the docs-only PR implementing #1314
(what-is-vultron.md explanation page), 5 pre-existing bugs were found in
unrelated implementation files. None are in the files changed by the PR.

New findings → issues filed:

1. **vultron/core/use_cases/received/embargo.py:266** — `InviteToEmbargoOnCaseReceivedUseCase`
   falls back to `dl.actor_id` as `invitee_id` when `receiving_actor_id` is
   `None`, silently signing the case actor into its own embargo invitation.
   Filed as #2762.

2. **vultron/core/behaviors/case/nodes/participant/common.py:410** —
   `_upgrade_participant_to_accepted` logs a misleading SM-04-001 warning on
   idempotent `RM.ACCEPTED` replay, filling logs with noise and masking real
   violations. Filed as #2763.

3. **test/ci/invariants/common.py:941** — `check_causal_edges` yields false
   negatives when ledger entries are missing `log_index` (`log_index()` returns
   `--1`), silently passing an invalid ordering check. Filed as #2764.

Already-tracked findings (not re-filed):

1. **vultron/core/behaviors/status/nodes/cs_dimension_filter.py:223** —
   `FilterCsPxaDimensionNode` in-place mutation pattern. Tracked as #2706.

2. **vultron/core/behaviors/embargo/nodes/lifecycle.py:373** —
   `SetEmbargoActiveNode` TOCTOU (concurrent double-emit of ledger entries
   when idempotency check and `activate_embargo()` read `VulnerabilityCase`
   independently). No dedicated issue yet; related to #2742 (ValueError escape
   from `activate_embargo()`). Tracked in
   `20260827-code-review-2109-deferred-preexisting.md` item #2.

## Audit disposition (2026-09-02)

Discharged: #2706, #2742, #2762, #2763, #2764.
