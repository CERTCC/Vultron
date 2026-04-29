---
title: "SPEC-AUDIT-3 \u2014 Fix Stale Spec References"
type: implementation
date: '2026-03-30'
source: SPEC-AUDIT-3
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3650
legacy_heading: "SPEC-AUDIT-3 \u2014 Fix Stale Spec References (COMPLETE 2026-03-30)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-30'
---

## SPEC-AUDIT-3 — Fix Stale Spec References

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3650`
**Canonical date**: 2026-03-30 (git blame)
**Legacy heading**

```text
SPEC-AUDIT-3 — Fix Stale Spec References (COMPLETE 2026-03-30)
```

**Legacy heading dates**: 2026-03-30

**Task**: Relocate transient implementation notes from specs and fix outdated
stale references found during the 2026-03-30 gap analysis.

### Changes Made

**Stale test path references** — updated `test/api/v2/` → canonical current
paths in 9 spec files:

- `dispatch-routing.md`: `test/api/v2/backend/test_dispatch_routing.py`
  → `test/test_behavior_dispatcher.py`, `test/test_semantic_handler_map.py`
- `handler-protocol.md`: `test/api/v2/backend/test_handlers.py`
  → `test/core/use_cases/received/`, `test/test_semantic_handler_map.py`
- `error-handling.md`: `test/api/v2/backend/test_error_handling.py`
  → `test/adapters/driving/fastapi/test_error_handling.py` (future)
- `inbox-endpoint.md`, `message-validation.md`, `http-protocol.md`:
  `test/api/v2/routers/test_actors.py`
  → `test/adapters/driving/fastapi/routers/test_actors.py`
- `structured-logging.md`: `test/api/v2/test_logging.py`
  → `test/adapters/driving/fastapi/test_logging.py` (future)
- `observability.md`: `test/api/v2/routers/test_health.py`
  → `test/adapters/driving/fastapi/routers/test_health.py`
- `response-format.md`: `test/api/v2/backend/test_response_generation.py`
  → `test/adapters/driving/fastapi/test_response_generation.py` (future)
- `idempotency.md`: `test/api/v2/backend/test_idempotency.py`
  → `test/core/test_idempotency.py` (future)
- `outbox.md`: `test/api/v2/backend/test_outbox.py`
  → `test/adapters/driving/fastapi/test_outbox.py`

**`SEMANTIC_HANDLER_MAP` → `USE_CASE_MAP`** — updated in 3 spec files:

- `handler-protocol.md`: HP-03-001 description, verification section
- `semantic-extraction.md`: SE-05-002 requirement text, verification section

**`@verify_semantics` decorator** — removed/updated in 3 spec files:

- `behavior-tree-integration.md`: BT-04-001 verification criterion updated
  to reference `USE_CASE_MAP` dispatch
- `architecture.md`: ARCH-07-001 "current state" note updated to describe
  current dispatch-time validation via `USE_CASE_MAP`
- `testability.md`: TB-05-005 rationale updated to reference `USE_CASE_MAP`

**Stale implementation paths** — updated in 5 spec files:

- `code-style.md`: CS-05-001 updated core/app layer boundaries
  (`vultron/behavior_dispatcher.py` removed; `api/v2/*` → `vultron/adapters/`)
- `semantic-extraction.md`: Related section updated to current dispatcher path
- `error-handling.md`: Related section updated to `fastapi/errors.py`
- `outbox.md`: Related section updated to delivery_queue and outbox_handler
- `idempotency.md`: Implementation section updated to current DataLayer port
- `response-format.md`: Related section updated to core use_cases

**TB-04-001 test structure** — updated mirror paths in `testability.md`
to reflect current `test/adapters/`, `test/core/`, `test/wire/` layout.

**Tests:** 1080 passed, 5581 subtests passed (no code changes; docs only).
