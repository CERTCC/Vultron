# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate 
insights, issues, and learnings during the implementation process.

Append new notes below this line.

---

## 2026-02-20: Agent test-suite efficiency fix

Agents were running `pytest` multiple times with slightly different flags
(`-q`, `tail -3`, `tail -15`, `grep -E "passed|failed"`) to extract counts
and failure info separately. This is wasteful.

**Fix**: Strengthened the one-run rule in root `AGENTS.md` (added explicit
`⚠️` warning block with the exact anti-patterns to avoid) and created
`test/AGENTS.md` with the same rule — so agents see the guidance when they
navigate into the `test/` directory.

The canonical command remains:

```bash
uv run pytest --tb=short 2>&1 | tail -5
```

---

## 2026-02-20: Spec Updates — New case-management.md and idempotency.md

Two specs were added/consolidated since the last plan revision:

**`specs/case-management.md`** (NEW):
- Formalizes requirements from `plan/PRIORITIES.md` (Priority 100, 200) and
  `notes/case-state-model.md` into testable specs.
- Key new requirement: **CM-04** mandates correct scoping of state updates:
  - RM state transitions → `ParticipantStatus.rm_state` (participant-specific)
  - EM state transitions → `CaseStatus.em_state` (shared per case)
  - PXA state transitions → `CaseStatus.pxa_state` (shared per case)
  - VFD state transitions → `ParticipantStatus.vfd_state` (participant-specific)
- Before implementing any state-changing handler, consult `notes/case-state-model.md`
  "Participant-Specific vs. Participant-Agnostic States" section.

**`specs/idempotency.md`** (CONSOLIDATED, now standalone):
- Previously scattered across inbox-endpoint.md, message-validation.md,
  handler-protocol.md. Now the authoritative source.
- **ID-04-004 is MUST**: state-changing handlers MUST be idempotent (not just SHOULD).
  This applies to any handler that transitions RM, EM, or CS state.
- Pattern: check current state before transitioning; if already in target state, log
  at INFO and return without side effects.

## 2026-02-20: BT-2.0 — CM-04 + ID-04-004 Compliance Audit COMPLETE

**BT-2.0.1 & BT-2.0.2 (verification)**: Confirmed `engage_case` and
`defer_case` handlers correctly update `ParticipantStatus.rm_state` (via
`_find_and_update_participant_rm` in `nodes.py`) and do not touch `CaseStatus`.
No code change needed.

**BT-2.0.3 & BT-2.0.4 (idempotency guards)**: Added idempotency check to
`_find_and_update_participant_rm` helper in `vultron/behaviors/report/nodes.py`.
Before appending a new `ParticipantStatus`, the helper checks if the latest
entry already has the target RM state. If so, it logs at INFO and returns
SUCCESS without side effects, satisfying ID-04-004 MUST.

**BT-2.0.5 (tests)**: Added two new tests to
`test/behaviors/report/test_prioritize_tree.py`:
- `test_engage_case_tree_idempotent`: runs EngageCaseBT twice; verifies
  exactly one ACCEPTED entry and final state is ACCEPTED.
- `test_defer_case_tree_idempotent`: runs DeferCaseBT twice; verifies
  exactly one DEFERRED entry and final state is DEFERRED.

Total test count: 474 passed, 2 xfailed (was 472).

**Pattern for future BTs**: Use the same helper-level idempotency check rather
than adding a dedicated BT node. This avoids BT tree complexity while still
satisfying ID-04-004.

---

## 2026-02-20: Test Speed — Parametrize demo tests

**Problem**: `test/scripts/test_receive_report_demo.py` had two tests that each
called `demo.main()` (all 3 demos), totalling 6 demo runs and ~24s wall time.

**Fix**:
- Added `demos` parameter to `main()` (optional sequence of callables; defaults
  to all three). Extracted `_ALL_DEMOS` registry so the loop is data-driven.
- Replaced the two monolithic tests with a single `@pytest.mark.parametrize`
  test over the three demo functions, each calling
  `demo.main(skip_health_check=True, demos=[demo_fn])`.
- Result: 3 demo runs instead of 6; wall time drops from ~24s to ~13s.
- Removed unused imports from the test file.

---


## 2026-02-20: BT-3 — Case Management Handlers COMPLETE

**BT-3.1 (create_case BT handler)**:
- Added `vultron/behaviors/case/` package with `nodes.py` and `create_tree.py`.
- `CreateCaseBT` follows the same Selector pattern as `ValidateReportBT`:
  - First child: `CheckCaseAlreadyExists` returns SUCCESS if case already in
    DataLayer (idempotency early exit per ID-04-004).
  - Second child: `CreateCaseFlow` Sequence — validate → persist → CaseActor
    → emit activity → update outbox.
- Idempotency naming: used `CheckCaseAlreadyExists` (SUCCESS when case exists)
  rather than `CheckCaseNotExists` from the plan because the Selector pattern
  requires the early-exit node to return SUCCESS on the already-done condition.
- `CreateCaseActorNode` creates the CaseActor with `context=case_id` and
  `attributed_to=actor_id` per CM-02-001.
- `execute_with_setup` called with `activity=None` when activity is not needed
  by any node in the tree (case and actor data carried via constructor args).

**BT-3.2 (add_report_to_case procedural)**:
- Rehydrates both report and case from the Add activity payload.
- Idempotency: checks existing `vulnerability_reports` before appending.

**BT-3.3 (close_case procedural)**:
- Handles Leave(VulnerabilityCase) by creating an RmCloseCase activity.
- Idempotent: catches `ValueError` on duplicate activity creation.
- Outbox update skipped gracefully if actor has no outbox attribute.

**Tests**: 8 new tests in `test/behaviors/case/test_create_tree.py`.
Total: 483 passed (was 474), 2 xfailed.

---

---

## Technical Debt: Object IDs Should Be URL-Like, Not Bare UUIDs

**Context**: The `/datalayer/{key}` route and `datalayer.read(key)` use the
object's `as_id` as the lookup key. When objects are created without an
explicit `id`, `generate_new_id()` returns a bare UUID-4 string (e.g.,
`2196cbb2-fb6f-407c-b473-1ed8ae806578`) rather than a full URL (e.g.,
`https://vultron.example/participants/2196cbb2-...`).

**Why bare UUIDs were used**: The initial implementation deliberately used bare
UUIDs to avoid URL-encoding/escaping issues when using object IDs as path
segments in API routes (a full URL contains `/` characters that would require
percent-encoding as `%2F` in the path, or a different route design).

**What should be done**: Object IDs should be proper URL-like identifiers (per
ActivityStreams spec). The API routes should accept URL-encoded IDs or use a
different lookup mechanism (e.g., query parameter `?id=<url>`, or base64url
encoding the ID in the path).

**Affected areas**:
- `generate_new_id()` in `vultron/as_vocab/base/utils.py` — add a
  `prefix` default based on object type
- Demo scripts and tests that assert on `as_id` format
- `/datalayer/{key}` route in `vultron/api/v2/routers/datalayer.py`
- Any handler that constructs participant or case IDs inline
