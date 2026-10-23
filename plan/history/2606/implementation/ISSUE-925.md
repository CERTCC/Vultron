---
source: ISSUE-925
timestamp: '2026-06-12T17:40:40.047874+00:00'
title: CI case-log invariant assertion harness (xfail ratchet)
type: implementation
---

## Issue #925 — CI case-log invariant assertion harness (xfail ratchet)

Implemented the xfail-ratchet invariant harness for canonical case-log
validation across the two-actor demo's JSONL replica artifacts.

### What was built

- `test/ci/test_case_log_invariants.py`: 11 discrete pytest functions, one
  per canonical-log invariant. A module-scoped `case_log_replicas` fixture
  loads all `*-case-log.jsonl` files from `devlogs/` (grouped by actor name,
  sorted by `log_index`) and skips the entire module when the directory is
  absent — safe in regular unit-test runs.
- `test/ci/README-case-log-ratchet.md`: ratchet workflow documentation (AC-6)
  covering how to add invariants, flip xfails to passing, and the CI behavior
  table.
- `pyproject.toml`: registered the new `case_log_invariants` pytest marker
  for targeted CI selection (`uv run pytest -m case_log_invariants`).
- `.github/workflows/demo-integration.yml`: three new steps after the JSONL
  upload — Python setup, dependency install, and invariant harness run —
  all dependency-chained with `id:` + `outcome == 'success'` guards to
  prevent false failures on infrastructure issues.

### Invariant status at merge

| # | Description | Status |
|---|-------------|--------|
| 1 | Local hash-chain consistency | ✅ passing today |
| 2 | Cross-actor entryHash agreement | ⏳ xfail (#789) |
| 3 | Cross-actor payloadSnapshot.actor agreement | ⏳ xfail (#789) |
| 4 | Non-empty payloadSnapshot for recorded entries | ⏳ xfail (#789) |
| 5 | All expected protocol eventTypes present | ⏳ xfail (#789) |
| 6 | No RM-state oscillation after CLOSED | ⏳ xfail (#789) |
| 7 | Log terminates with all participants RM=CLOSED | ⏳ xfail (#789) |
| 8 | Late-joiner has full pre-join history | ⏳ xfail (#791) |
| 9 | ParticipantStatus schema completeness | ⏳ xfail (#789) |
| 10 | Nested objects inlined in payloadSnapshot | ⏳ xfail |
| 11 | payloadSnapshot.context uses case URI | ⏳ xfail |

### Notes

- Pre-commit code review caught two issues: (1) hash-chain invariant would
  false-positive on missing `entryHash`/`prevLogHash` fields — fixed by
  asserting field presence before comparing; (2) CI workflow step ordering
  allowed the pytest step to run when install failed — fixed with `id:` +
  `outcome == 'success'` chaining.
- 3205 unit tests pass; 11 new invariant tests skip cleanly when
  `devlogs/` is absent.

PR: [#936](https://github.com/CERTCC/Vultron/pull/936)
