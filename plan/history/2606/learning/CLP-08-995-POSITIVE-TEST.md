---
source: CLP-08-995-POSITIVE-TEST
timestamp: '2026-06-22T19:36:27.445959+00:00'
title: Positive ledger tests must assert CaseLedger.entries grows by one
type: learning
---

When writing positive tests for case-ledger commit paths, always assert
`len(case.case_ledger.entries) == N+1` after the commit, not just that no
exception was raised. A use case that short-circuits before committing passes
an exception-only assertion but silently breaks ledger continuity. The
`entries` length assertion is the only check that reliably distinguishes a
genuine commit from an early-exit no-op.

**Promoted**: 2026-06-22 — captured in `test/AGENTS.md` (Positive Ledger
Commit Assertions section).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
