---
source: ISSUE-1484
timestamp: '2026-07-21T15:57:33.913070+00:00'
title: 'Close #1484 — P/X/A received-embargo guards already implemented'
type: implementation
---

## Issue #1484 — Add P/X/A embargo-eligibility guard to received embargo path (EMB-01-002, EMB-02-002)

All implementable ACs (AC-1, AC-2, AC-4) were already satisfied by commit `587a01ece` on main before this build run. `InviteToEmbargoOnCaseReceivedUseCase` and `AcceptInviteToEmbargoOnCaseReceivedUseCase` both contain `_pxa_embargo_ineligible()` pre-flight guards that reject the inbound EP/EA with an ER when P/X/A is set. 39 unit tests covering the blocked path pass in `test/core/use_cases/received/test_embargo_propose_accept_reject.py`. AC-3 (full EmbargoLifecycle STRICT-mode migration for received-side EM transitions) remains pending on #747 as noted in the issue itself. Issue closed with comment referencing the implementing commit.
