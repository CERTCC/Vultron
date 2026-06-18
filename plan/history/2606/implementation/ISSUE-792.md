---
source: ISSUE-792
timestamp: '2026-06-18T18:27:29.915264+00:00'
title: Remove CaseEvent model and record_event()
type: implementation
---

## Issue #792 — Deprecate and remove CaseEvent path after canonical convergence

Completed the final step of Epic #788 by removing the legacy `CaseEvent`
model (`vultron/core/models/case_event.py`) and the
`VulnerabilityCase.record_event()` / `events` field. All protocol-significant
history is now served exclusively by the canonical `CaseLedgerEntry` hash
chain. No production logic depended on `case.events` writes at the time of
removal; all write-path call sites had been migrated in #789.

Changes:

- Deleted `vultron/core/models/case_event.py` and the `VultronCaseEvent` alias
- Removed `events: list[CaseEvent]` field and `record_event()` from
  `VulnerabilityCase` in `vultron/core/models/case.py`
- Removed `events: list` from `CaseModel` Protocol in `protocols.py`
- Removed `CaseEvent`/`VultronCaseEvent` from `vultron_types.py`
- Deleted `test/core/models/test_case_event.py` and
  `test/wire/as2/vocab/test_case_event.py`
- Removed `TestVulnerabilityCaseRecordEvent` class from `test/core/models/test_case.py`
- Updated `notes/case-state-model.md`, `notes/case-ledger-authority.md`,
  `notes/sync-ledger-replication.md`, `notes/codebase-structure.md`,
  `notes/README.md`, and `vultron/core/AGENTS.md` to reflect the removal and
  mark Epic #788 complete

3446 unit tests pass (13 `CaseEvent`-specific tests removed). All linters
(Black, flake8, mypy, pyright) clean.

PR: [#1042](https://github.com/CERTCC/Vultron/pull/1042)
