---
title: 'CA-2 follow-up: actor-first case-scoped action-rules endpoint'
type: implementation
date: '2026-03-25'
source: LEGACY-2026-03-25-ca-2-follow-up-actor-first-case-scoped-action-ru
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3380
legacy_heading: 'CA-2 follow-up: actor-first case-scoped action-rules endpoint'
date_source: git-blame
---

## CA-2 follow-up: actor-first case-scoped action-rules endpoint

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3380`
**Canonical date**: 2026-03-25 (git blame)
**Legacy heading**

```text
CA-2 follow-up: actor-first case-scoped action-rules endpoint
```

**Completed**: Reworked the CA-2 action-rules contract to use the final
actor-first, case-scoped route:
`GET /actors/{actor_id}/cases/{case_id}/action-rules`.

**What changed**:

- `vultron/adapters/driving/fastapi/routers/actors.py`: replaced the prior
  action-rules shape with the actor-first case-scoped endpoint.
- `vultron/core/use_cases/action_rules.py`: simplified `ActionRulesRequest` to
  `(case_id, actor_id)` and resolved the matching `CaseParticipant`
  internally via `actor_participant_index` with a fallback scan of
  `case.case_participants`.
- `vultron/core/models/protocols.py`: tightened the protocol typing used by
  the action-rules use case so the new logic remains core-friendly and avoids
  wire imports.
- `test/core/use_cases/test_action_rules.py` and
  `test/adapters/driving/fastapi/routers/test_actors.py`: updated unit and
  router coverage to validate the actor/case contract, including 404 behavior
  for unknown cases and actors not participating in the selected case.
- `specs/case-management.yaml` and `specs/agentic-readiness.yaml`: updated to
  document the final actor-first case-scoped endpoint and the internal
  actor→participant resolution behavior.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/`
- `markdownlint-cli2 --fix --config .markdownlint-cli2.yaml "**/*.md"`
- `uv run pytest --tb=short 2>&1 | tail -5` → `1021 passed, 5581 subtests passed`
