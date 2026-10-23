---
title: 'CA-2: Action Rules Endpoint (PRIORITY-200)'
type: implementation
timestamp: '2026-03-25T00:00:00+00:00'
source: CA-2
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3354
legacy_heading: 'CA-2: Action Rules Endpoint (PRIORITY-200)'
date_source: git-blame
---

## CA-2: Action Rules Endpoint (PRIORITY-200)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3354`
**Canonical date**: 2026-03-25 (git blame)
**Legacy heading**

```text
CA-2: Action Rules Endpoint (PRIORITY-200)
```

**Completed**: Implemented `GET /actors/{case_actor_id}/action-rules?participant={actor_id}`
endpoint returning valid CVD actions for a named participant given the current
combined case state (RM, EM, CS_vfd, CS_pxa).

**Files changed**:

- `vultron/core/use_cases/action_rules.py` (new): `ActionRulesRequest` model
  and `GetActionRulesUseCase` class. Resolves CaseActor → VulnerabilityCase →
  CaseParticipant, reads per-participant RM/VFD state and shared case EM/PXA
  state, builds the 6-char CS state string, and returns valid CVD actions via
  `potential_actions.action()`.
- `vultron/adapters/driving/fastapi/routers/actors.py`: Added
  `GET /{case_actor_id}/action-rules` endpoint (positioned before inbox to
  avoid path conflicts).
- `test/core/use_cases/test_action_rules.py` (new): Unit tests for
  `GetActionRulesUseCase` covering happy path, default states, error paths,
  and EM state variations.
- `test/adapters/driving/fastapi/routers/test_actors.py`: Added endpoint
  integration tests (200, 404, 422).

**Specs implemented**: CM-07-001, CM-07-002, CM-07-003, AR-07-001, AR-07-002.
