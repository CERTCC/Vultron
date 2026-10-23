---
source: ISSUE-995
timestamp: '2026-06-18T18:57:53.315794+00:00'
title: Per-case genesis hash origin binding (CLP-08)
type: implementation
---

## Issue #995 — Implement per-case genesis hash origin binding (CLP-08)

Replaced the global `GENESIS_HASH = "0" * 64` sentinel with a per-case genesis
hash derived from case-specific metadata (SHA-256 of case_id + "|" +
created_at.isoformat() + "|" + case_actor_id), cryptographically anchoring each
case ledger to its origin identity and timestamp (CLP-08-001, CLP-08-002).

### What was implemented

- `compute_genesis_hash(case_id, created_at, case_actor_id)` added to
  `vultron/core/models/case_ledger.py`; global `GENESIS_HASH` constant removed
- `CaseLedger.__init__` updated to require `genesis_hash: str`; `tail_hash` and
  `verify_chain` use `self._genesis_hash` (CLP-08-004)
- `genesis_hash: str` field added to core and wire `VulnerabilityCase` with a
  `model_validator` that auto-computes at construction from `id_`, `published`,
  and `attributed_to` (CLP-08-003); wire model uses only `published` (not
  `updated` fallback) to avoid divergence with the CaseActor's computed hash
- `_get_case_genesis_hash(case_id, dl)` added to `sync_helpers`; duck-typed via
  `getattr` to avoid importing wire types from core; `is_ledger_fresh_for_case`
  updated with optional `genesis_hash` parameter; `_reconstruct_tail_hash` uses
  per-case genesis when ledger is empty (CLP-08-005)
- `last_acknowledged_hash`, `last_accepted_hash`, and `prev_log_hash` defaults
  all updated to `""` (empty string) across models
- 18 test files updated; positive CLP-08-004 coverage added in
  `test/core/test_sync_helpers.py::TestContiguousChain::test_per_case_genesis_hash_chain_is_fresh`

### Outcome

All 3705 tests pass (1 new). Black, flake8, mypy, pyright clean.
PR: [#1048](https://github.com/CERTCC/Vultron/pull/1048)
