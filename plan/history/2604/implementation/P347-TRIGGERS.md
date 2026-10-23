---
title: "P347-TRIGGERS \u2014 New Trigger Endpoints (create-case, add-report-to-case,\
  \ suggest-actor-to-case, accept-case-invite)"
type: implementation
timestamp: '2026-04-20T00:00:00+00:00'
source: P347-TRIGGERS
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6833
legacy_heading: "P347-TRIGGERS \u2014 New Trigger Endpoints (create-case,\
  \ add-report-to-case, suggest-actor-to-case, accept-case-invite)"
date_source: git-blame
---

## P347-TRIGGERS — New Trigger Endpoints (create-case, add-report-to-case, suggest-actor-to-case, accept-case-invite)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6833`
**Canonical date**: 2026-04-20 (git blame)
**Legacy heading**

```text
P347-TRIGGERS — New Trigger Endpoints (create-case, add-report-to-case, suggest-actor-to-case, accept-case-invite)
```

**Completed:** P347-TRIGGERS from PRIORITY-347 (Demo Puppeteering, Trigger Completeness, BT Generalization)

### Summary

Added four new trigger endpoints that allow actors to initiate case-related
protocol actions without requiring direct inbox injection (enabling
puppeteering over spoofing in demos).

### Changes

**New domain request models** (`vultron/core/use_cases/triggers/requests.py`):

- `CreateCaseTriggerRequest` — `actor_id`, `name`, `content`, `report_id?`
- `AddReportToCaseTriggerRequest` — `actor_id`, `case_id`, `report_id`
- `SuggestActorToCaseTriggerRequest` — `actor_id`, `case_id`, `suggested_actor_id`
- `AcceptCaseInviteTriggerRequest` — `actor_id`, `invite_id`

**New HTTP request body models** (`vultron/adapters/driving/fastapi/trigger_models.py`):

- `CreateCaseRequest`, `AddReportToCaseRequest`, `SuggestActorToCaseRequest`, `AcceptCaseInviteRequest`

**New use cases** (`vultron/core/use_cases/triggers/case.py`):

- `SvcCreateCaseUseCase` — creates `VulnerabilityCase` + `CreateCaseActivity` → outbox
- `SvcAddReportToCaseUseCase` — creates `AddReportToCaseActivity` → outbox

**New use cases** (`vultron/core/use_cases/triggers/actor.py`, new file):

- `SvcSuggestActorToCaseUseCase` — creates `RecommendActorActivity` → outbox
- `SvcAcceptCaseInviteUseCase` — reads invite, coerces to `RmInviteToCaseActivity`, creates `RmAcceptInviteToCaseActivity` → outbox

**New adapter functions** (`vultron/adapters/driving/fastapi/_trigger_adapter.py`):

- `create_case_trigger`, `add_report_to_case_trigger`, `suggest_actor_to_case_trigger`, `accept_case_invite_trigger`

**Router updates**:

- `trigger_case.py` — added `POST /{actor_id}/trigger/create-case` and `POST /{actor_id}/trigger/add-report-to-case`
- `trigger_actor.py` — new file with `POST /{actor_id}/trigger/suggest-actor-to-case` and `POST /{actor_id}/trigger/accept-case-invite`
- `v2_router.py` — registered `trigger_actor.router`

**Tests**:

- `test_trigger_case.py` — added 13 tests for create-case and add-report-to-case
- `test_trigger_actor.py` — new file with 13 tests for suggest-actor-to-case and accept-case-invite

### Test Result

1652 passed, 12 skipped, 182 deselected, 5581 subtests passed
