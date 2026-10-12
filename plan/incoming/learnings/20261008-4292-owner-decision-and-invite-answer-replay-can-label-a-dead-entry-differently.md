---
title: >-
  A received decision that commits one entry but applies a different register
  step to its own store diverges from a replica that replays that entry
type: learning
timestamp: "2026-10-08T18:40:00Z"
source: ISSUE-4292
signal: theme-candidate
---

**Trigger.** A received or owner-decision tree commits ledger entry X, but its
effects apply a different register transition than replaying X would.

**Claim.** ADR-0124 makes a replica the replay of its ledger, so the author's
register and the replica's must agree entry by entry. When the committed entry
and the applied effect differ, the two sides can label the same terminal entry
differently while EM, `active_embargo`, and signatory reads still converge. EM
convergence is necessary, not sufficient, and the usual tests check only EM.

**Evidence.** The owner Reject of the last open revision after disclosure
(EMB-04-002) committed `reject_embargo_proposal_on_case` then ran
`terminate_embargo_bt`: the CASE_MANAGER ended CANCELLED, a replica REJECTED.
Filed and fixed as #4364.

**How to apply.** For such a tree, add a convergence test that rebuilds the
author's own case from its ledger and asserts register equality, not just EM
equality. See `test/core/use_cases/received/test_ledger_replay_convergence.py`
and `notes/embargo-lifecycle.md`.

**What would confirm it.** A second commit/effect mismatch in a different tree
(not the embargo owner-decision path) that converges on EM but diverges on a
terminal entry's status.
