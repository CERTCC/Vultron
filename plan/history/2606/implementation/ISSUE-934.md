---
source: ISSUE-934
timestamp: '2026-06-12T19:37:45.105847+00:00'
title: Rename Case Log → Case Ledger across codebase
type: implementation
---

## Issue #934 — Rename Case Log → Case Ledger across codebase (terminology + file paths + wire types)

Applied the "Case Log → Case Ledger" terminology rename from ADR-0019 across
all code, specs, notes, and docs in the Vultron repository.

### What was renamed

- **Classes**: `HashChainLogRecord` → `HashChainLedgerRecord`, `CaseEventLog` → `CaseLedger`,
  `CaseLogEntry` → `CaseLedgerEntry` (core + wire), `VultronCaseLogEntry` → `VultronCaseLedgerEntry`,
  `VultronCaseLogEntryRef` → `VultronCaseLedgerEntryRef`,
  `CommitCaseLogEntryNode` → `CommitCaseLedgerEntryNode`,
  `CollectAndSortCaseLogEntriesNode` → `CollectAndSortCaseLedgerEntriesNode`
- **Wire type identifier**: `"CaseLogEntry"` → `"CaseLedgerEntry"` (breaking serialization change)
- **Files (git mv)**: `case_log.py` → `case_ledger.py`, `case_log_entry.py` → `case_ledger_entry.py`,
  `wire/objects/case_log_entry.py` → `case_ledger_entry.py`,
  `specs/case-log-processing.yaml` → `specs/case-ledger-processing.yaml`,
  `specs/sync-log-replication.yaml` → `specs/sync-ledger-replication.yaml`,
  `notes/case-log-authority.md` → `notes/case-ledger-authority.md`,
  `notes/sync-log-replication.md` → `notes/sync-ledger-replication.md`,
  plus matching test file renames
- **pytest mark**: `case_log_invariants` → `case_ledger_invariants` in `pyproject.toml`
- **All imports, docstrings, specs, notes, docs** updated across ~114 files
- **ADR-0018 title preserved** (immutable published ADR)

### Verification

- 3205 unit tests pass; Black, flake8, mypy, pyright all clean
- `grep` for all old names returns zero hits outside ADR-0018 and plan/history

PR: [#940](https://github.com/CERTCC/Vultron/pull/940)
