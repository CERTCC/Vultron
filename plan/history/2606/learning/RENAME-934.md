---
source: RENAME-934
timestamp: '2026-06-22T19:33:46.546876+00:00'
title: pytest mark registration must mirror class/file renames in CI workflows
type: learning
---

When renaming a pytest mark (e.g., `case_log_invariants` → `case_ledger_invariants`),
update **both** `pyproject.toml` markers AND any `.github/workflows/` YAML files that
reference the mark by name. A renamed mark in test files without a corresponding
workflow update causes `pytest` to select 0 tests and exit with code 5 (no tests
collected), failing CI even though the rename itself is correct.

**Promoted**: 2026-06-22 — captured in `specs/testability.yaml` (TB-11-001) and
`test/AGENTS.md` (Pytest Mark Consistency section).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
