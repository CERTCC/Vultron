---
source: ISSUE-1749
timestamp: '2026-08-08T01:35:24.980187+00:00'
title: 'test(case-proposal): dual-DL isolation guard'
type: implementation
---

## Issue #1749 — test(case-proposal): use dual-DataLayer setup in TestCreateCaseProposalReceivedBTCaseActorRecords

Added `TestCreateCaseProposalReceivedBTCaseActorRecords` to `test/core/behaviors/case/test_case_proposal_received_tree.py`. The class contains 4 tests that run `CreateCaseProposalReceivedUseCase` against an injected `case_actor_dl` and then assert the global singleton returned by `get_datalayer()` is empty for `VulnerabilityCase`, `CaseParticipant`, `CaseLedgerEntry`, and `actor_participant_index`. This catches the regression class where a BT node calls `get_datalayer()` instead of `self.datalayer`, which prior single-DL tests could not detect.

PR: <https://github.com/CERTCC/Vultron/pull/2124>
