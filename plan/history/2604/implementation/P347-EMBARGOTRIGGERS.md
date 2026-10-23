---
title: "P347-EMBARGOTRIGGERS \u2014 Embargo Trigger Rename + Accept/Reject/Revision"
type: implementation
timestamp: '2026-04-20T00:00:00+00:00'
source: P347-EMBARGOTRIGGERS
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6887
legacy_heading: "P347-EMBARGOTRIGGERS \u2014 Embargo Trigger Rename + Accept/Reject/Revision"
date_source: git-blame
---

## P347-EMBARGOTRIGGERS — Embargo Trigger Rename + Accept/Reject/Revision

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6887`
**Canonical date**: 2026-04-20 (git blame)
**Legacy heading**

```text
P347-EMBARGOTRIGGERS — Embargo Trigger Rename + Accept/Reject/Revision
```

### Task

Rename `evaluate-embargo` trigger endpoint → `accept-embargo`, add
`reject-embargo` and `propose-embargo-revision` trigger endpoints across all
layers (core use cases, FastAPI router, MCP server, tests, specs).

### Changes

**Core layer:**

- `vultron/core/use_cases/triggers/requests.py`: Renamed
  `EvaluateEmbargoTriggerRequest` → `AcceptEmbargoTriggerRequest`; added
  `RejectEmbargoTriggerRequest` and `ProposeEmbargoRevisionTriggerRequest`;
  backward-compat alias preserved.
- `vultron/core/use_cases/triggers/embargo.py`: Renamed
  `SvcEvaluateEmbargoUseCase` → `SvcAcceptEmbargoUseCase`; added
  `SvcRejectEmbargoUseCase` (PROPOSED→NO_EMBARGO / REVISE→ACTIVE EM
  transition, emits `EmRejectEmbargoActivity`); added
  `SvcProposeEmbargoRevisionUseCase` (ACTIVE/REVISE only, PROPOSE EM
  transition, emits `EmProposeEmbargoActivity`); backward-compat alias
  preserved.

**Adapter layer:**

- `vultron/adapters/driving/fastapi/trigger_models.py`: Renamed
  `EvaluateEmbargoRequest` → `AcceptEmbargoRequest`; added
  `RejectEmbargoRequest` and `ProposeEmbargoRevisionRequest`.
- `vultron/adapters/driving/fastapi/_trigger_adapter.py`: Renamed
  `evaluate_embargo_trigger` → `accept_embargo_trigger`; added
  `reject_embargo_trigger` and `propose_embargo_revision_trigger`.
- `vultron/adapters/driving/fastapi/routers/trigger_embargo.py`: Renamed
  `evaluate-embargo` → `accept-embargo` endpoint; added `reject-embargo` and
  `propose-embargo-revision` endpoints.
- `vultron/adapters/driving/mcp_server.py`: Renamed `mcp_evaluate_embargo` →
  `mcp_accept_embargo`; added `mcp_reject_embargo` and
  `mcp_propose_embargo_revision`; updated `MCP_TOOLS` list.

**Tests:**

- `test/adapters/driving/fastapi/routers/test_trigger_embargo.py`: Renamed
  all `evaluate-embargo` URL references to `accept-embargo`; added ~20 new
  tests for `reject-embargo` and `propose-embargo-revision` endpoints.
- `test/core/use_cases/received/test_embargo.py`: Updated imports.
- `test/core/use_cases/triggers/test_trignotify.py`: Updated imports.

**Specs:**

- `specs/triggerable-behaviors.yaml`: Updated `TRIG-02-002` table to show
  `accept-embargo`, `reject-embargo`, and `propose-embargo-revision`; updated
  `TRIG-03-001` case-scoped behaviors list.

### Test Result

1669 passed, 12 skipped, 182 deselected, 5581 subtests passed
