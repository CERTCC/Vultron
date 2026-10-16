---
title: "CM-23-018 skips a closed Case Owner's repeated Leave that CM-23-002 must run to finish a part-way closure"
type: learning
timestamp: "2026-10-16T19:30:00Z"
source: ISSUE-4522
signal: spec-contradiction
---

**Trigger.** You change how the CASE_MANAGER answers a `Leave(VulnerabilityCase)`
from a sender whose closure the ledger already records, or how a failed owner
closure heals.

**Claim.** Read on `main` before PR #4823, two MUSTs disagree for one state: a
Case Owner whose own closure is recorded, on a case that is not yet fully
closed (its CASE_MANAGER closure step failed to commit, CLP-07-013).

- CM-23-018 says a repeated act that would close an already-closed sender,
  a `Leave` included, MUST be reported `SKIPPED`: "its effect is already in
  place".
- CM-23-002 says that on a `Leave` from the Case Owner the CASE_MANAGER MUST
  run the whole closure sequence through `case_fully_closed`. The test
  `test_a_redelivered_owner_leave_completes_the_closure` relies on the
  redelivery finishing the closure.

For the Case Owner the effect is not in place until `case_fully_closed`, so
CM-23-018's own reason does not hold there.

**Evidence.** PR #4823 (#4522) adds the closed-sender pre-flight to the Leave
handler with `case_owner_completes=True`, and amends CM-23-018 with a Case Owner
exception. The PR is held as a draft for the maintainer's decision.

**How to apply.** If the maintainer rejects the amendment, the part-way owner
closure needs another way to heal (a CASE_MANAGER-side retry), and the heal test
changes with it.
