---
source: ISSUE-1385
timestamp: '2026-07-15T14:38:59.033004+00:00'
title: 'refactor: use CasePersistence in AcceptCaseProposalReceivedUseCase and RejectCaseProposalReceivedUseCase'
type: implementation
---

## Issue #1385 — refactor: use CasePersistence in AcceptCaseProposalReceivedUseCase and RejectCaseProposalReceivedUseCase

Migrated `AcceptCaseProposalReceivedUseCase` and `RejectCaseProposalReceivedUseCase` in `vultron/core/use_cases/received/case_proposal.py` from the broad `DataLayer` port to the narrow `CasePersistence` port, satisfying DL-03-001/DL-03-002. Removed the unused `DataLayer` import. All 4722 unit tests pass; Black, flake8, mypy, and pyright all clean.

PR: <https://github.com/CERTCC/Vultron/pull/1436>
