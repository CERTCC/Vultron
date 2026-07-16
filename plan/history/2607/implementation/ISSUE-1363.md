---
source: ISSUE-1363
timestamp: '2026-07-14T20:12:13.543406+00:00'
title: FVV late-joiner backfill miss
type: implementation
---

## Issue #1363 — FVV demo intermittent `test_invariant_8_late_joiner_has_full_history` failure

**Symptom**: `_phase_dump_case_ledgers` in the FVV demo occasionally captured a
gapped case ledger for the Finder replica (e.g. `logIndex=17` missing), causing
`test_invariant_8_late_joiner_has_full_history` to fail non-deterministically.

**Root cause**: `_phase_case_closure` waited only for the tail entry hash to
appear in the Finder's DataLayer before dumping logs. `Announce(CaseLedgerEntry)`
activities are delivered independently per entry; an intermediate entry can
arrive *after* the tail, so the JSONL dump was captured with a gap.

**Fix**: Added `wait_for_contiguous_ledger_coverage()` to `polling.py`. It polls
until the replica holds **all** log indices `0…expected_tail_index` before the
dump proceeds. Replaced both `wait_for_finder_log_entry()` call sites in the FVV
demo (Phase 2 sync verification and Phase 6 case closure) with this stronger gate.

**Files changed**:

- `vultron/demo/helpers/polling.py` — new helper
- `vultron/demo/helpers/__init__.py` — re-export
- `vultron/demo/scenario/fvv_demo.py` — use stronger gate
- `test/demo/test_fvv_demo.py` — 5 regression tests

PR: <https://github.com/CERTCC/Vultron/pull/1433>
