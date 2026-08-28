---
title: Code review of PR for #2109 surfaced 5 pre-existing bugs in unrelated files
type: learning
timestamp: 2026-08-27
source: ISSUE-2109
signal: deferred-bug
---

During the code review for PR implementing #2109 (fixname() prefix-map refactor),
5 pre-existing bugs were found in unrelated files. None are in the files changed
by the PR. These are DEFER items requiring follow-up issues.

1. **vultron/core/use_cases/triggers/actor.py:224** — ActorDiscovery backend.update()
   called without setup(), breaking directory-service backends that init resources in setup().

2. **vultron/core/behaviors/embargo/nodes/lifecycle.py:373** — SetEmbargoActiveNode
   TOCTOU: idempotency check and activate_embargo() read VulnerabilityCase independently;
   concurrent requests can double-emit ledger entries.

3. **vultron/core/behaviors/status/nodes/case_status.py:293** — AppendCaseStatusToCaseNode
   persists filtered CaseStatus to DataLayer before linking it to the case; if
   case.add_case_status() raises, the record is orphaned and original EM/PXA values are lost.

4. **vultron/core/behaviors/status/nodes/cs_dimension_filter.py:211** — FilterCsPxaDimensionNode
   mutates accumulator dict in-place relying on blackboard returning an object reference;
   fragile if blackboard ever returns deep-copies.

5. **vultron/core/behaviors/embargo/nodes/teardown.py:136** — ClearActiveEmbargoNode only
   catches VultronNotFoundError; if instantiated with default STRICT mode and EM.NONE,
   VultronInvalidStateTransitionError propagates uncaught and crashes the tree.

**Action:** Create Bug/Concern issues for each. Not in scope of #2109 PR.
