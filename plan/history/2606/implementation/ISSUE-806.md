---
source: ISSUE-806
timestamp: '2026-06-10T13:50:08.763802+00:00'
title: Rename hash-chain CaseLogEntry to HashChainLogRecord
type: implementation
---

## Issue #806 — Rename local hash-chain CaseLogEntry to eliminate naming ambiguity

Renamed `vultron.core.models.case_log.CaseLogEntry` → `HashChainLogRecord` to
eliminate confusion with the wire-serializable `CaseLogEntry(CoreObject)` in
`case_log_entry.py`. The hash-chain record is a local in-memory model used by
`CaseEventLog` for SYNC-1 processing and is never persisted or sent over the wire.

### Changes

- **case_log.py**: class renamed; docstring updated
- **chain.py**: import and 3 instantiations updated
- **sync.py** (triggers): import and 3 type signatures updated
- **conftest.py** (sync nodes): fixture updated
- **8 test files**: all imports and assertions updated
- **AGENTS.md**: pitfall entry updated with new name

### Outcome

All 3100 unit tests pass. All 4 linters clean.

PR: [https://github.com/CERTCC/Vultron/pull/857](https://github.com/CERTCC/Vultron/pull/857)
