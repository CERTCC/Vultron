---
source: CONCERN-2269
timestamp: '2026-08-13T01:00:42.254022+00:00'
title: append.py + effects.py decomposition eliminates BTND-07-004 churn
type: learning
---

Both `status/nodes/append.py` (499 lines) and `sync/nodes/effects.py` (495 lines)
were at the BTND-07-004 ceiling, causing any unrelated edit in those areas to
trigger a mandatory decomposition as a side-effect.

**Resolution**: Decomposed both modules by semantic concern in a single PR with
no backward-compatibility shims. All importers updated in-place.

## append.py → append/ subpackage

- `append/conditions.py` — 4 guard/idempotency nodes + `_has_status_in_participant` helper
- `append/actions.py` — 3 DataLayer-mutating action nodes
- `append/__init__.py` — re-exports all 7 public names (import paths unchanged)

## effects.py → per-class files + _helpers.py

- `_helpers.py` — `_extract_id_from_field` + `_LedgerEffectNode` base class
  (DRY: all 4 effect nodes shared identical `setup()` + `_require_log_entry` pattern)
- `participant_status_effect.py`, `note_effect.py`, `invite_accept_effect.py`,
  `close_case_effect.py` — one file per class

## Test mirroring

- `test_append.py` split into `append/conftest.py` + `test_conditions.py` + `test_actions.py`
- Added `TestCheckParticipantRMNotClosedNode` (was missing from original)
- `test_effects.py` split into 4 per-class test files
- Added tests for `ApplyNoteFromLedgerNode`, `ApplyInviteAcceptFromLedgerNode`,
  `ApplyCloseCaseFromLedgerNode` (all three were previously untested)

**PR**: <https://github.com/CERTCC/Vultron/pull/2282>

**5 other near-limit modules** noted as future work: `replay.py` (498),
`suggest_actor/emit.py` (498), `deploy_fix.py` (497),
`embargo/nodes/lifecycle.py` (494), `conditions.py` (488).
