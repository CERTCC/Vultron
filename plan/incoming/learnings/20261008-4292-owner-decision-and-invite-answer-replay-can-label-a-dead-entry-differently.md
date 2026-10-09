---
title: >-
  A received decision that commits one entry but applies a different register
  step to its own store diverges from a replica that replays that entry
type: learning
timestamp: "2026-10-08T18:40:00Z"
source: ISSUE-4292
signal: theme-candidate
---

## What happened

Issue #4292 split the case owner's embargo decision (its own
`Accept`/`Reject` of the EmbargoEvent) from the per-participant
`Accept`/`Reject` of the Invite. Review found a pre-existing convergence
defect in the owner-Reject path, carried verbatim from the old
Reject-of-the-Invite tree: when the owner rejects the **last open revision
after disclosure** (EMB-04-002), the CASE_MANAGER commits a
`reject_embargo_proposal_on_case` entry but then runs `terminate_embargo_bt`,
so its own register ends with the revision CANCELLED; a replica replaying that
same reject entry in OBSERVED mode does the plain REJECT step and ends
REJECTED. Filed as #4364.

## The lesson

ADR-0124 says a replica is the replay of its ledger, so the register a
CASE_MANAGER builds from its received-side effects must match the register a
replica builds by replaying the entry those effects committed. When a received
tree commits entry X but, in the same effects, applies a different transition
(here: commit a reject, then terminate) the two sides can label the same dead
entry differently. EM, active_embargo and signatory reads all converged (both
reached EXITED), which is exactly why it stayed invisible — the divergence is
only in a terminal entry's status, and no test rebuilt the manager's own case
from its ledger for this edge.

## How to apply

When a received or owner-decision tree's committed entry and its applied effect
are not the same transition, add a convergence test that rebuilds the author's
own case from its ledger and asserts register equality, not just EM equality.
EM convergence is necessary, not sufficient. See `notes/embargo-lifecycle.md`
and `test/core/use_cases/received/test_ledger_replay_convergence.py`.
