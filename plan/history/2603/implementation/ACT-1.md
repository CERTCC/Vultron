---
title: "ACT-1 \u2014 ADR for per-actor DataLayer isolation (2026-03-19)"
type: implementation
timestamp: '2026-03-19T00:00:00+00:00'
source: ACT-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2521
legacy_heading: "ACT-1 \u2014 ADR for per-actor DataLayer isolation (2026-03-19)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-19'
---

## ACT-1 — ADR for per-actor DataLayer isolation (2026-03-19)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2521`
**Canonical date**: 2026-03-19 (git blame)
**Legacy heading**

```text
ACT-1 — ADR for per-actor DataLayer isolation (2026-03-19)
```

**Legacy heading dates**: 2026-03-19

**Task**: Draft ADR-0012 for per-actor DataLayer isolation, resolving four
design decisions required before ACT-2 implementation can begin.

**What was done**:

- Created `docs/adr/0012-per-actor-datalayer-isolation.md` (status: accepted).
- Added ADR-0011 and ADR-0012 entries to `docs/adr/index.md` (ADR-0011 was
  previously missing from the index).
- Marked ACT-1 complete in `plan/IMPLEMENTATION_PLAN.md`.

**Decisions recorded**:

1. **DataLayer isolation strategy**: Option B — TinyDB namespace prefix (one
   table per `actor_id`) as the near-term prototype implementation, with
   MongoDB Community Edition as the concurrent production-grade target.
2. **`get_datalayer` FastAPI DI strategy**: Closure lambda —
   `Depends(lambda actor_id=Path(...): get_datalayer(actor_id))` — applied
   uniformly across all route files in ACT-3.
3. **`actor_io.py` inbox/outbox ownership**: Migrate inbox/outbox into the
   per-actor DataLayer as TinyDB collections (`{actor_id}_inbox`,
   `{actor_id}_outbox`); remove `actor_io.py` after ACT-2 (unblocks VCR-014).
4. **OUTBOX-1 scope boundary**: Defer OX-1.1–OX-1.4 until ACT-3 is complete
   to avoid implementing delivery against a still-changing DataLayer.

**Result**: 984 tests pass (no regressions; docs-only change).

---

### TECHDEBT-31 — Relocate `trigger_services/` into FastAPI adapter (2026-03-23)

**Task**: Move `vultron/api/v2/backend/trigger_services/` into the proper
FastAPI adapter layer under `vultron/adapters/driving/fastapi/`.

**What was done**:

- Moved `domain_error_translation()` and `translate_domain_errors()` from
  `trigger_services/_helpers.py` into
  `vultron/adapters/driving/fastapi/errors.py`.
- Moved HTTP request body models from `trigger_services/_models.py` to
  `vultron/adapters/driving/fastapi/trigger_models.py` (unchanged content).
- Merged all three thin adapter delegate modules (`case.py`, `embargo.py`,
  `report.py`) into a single
  `vultron/adapters/driving/fastapi/_trigger_adapter.py`.
- Updated all three trigger routers (`trigger_report.py`, `trigger_case.py`,
  `trigger_embargo.py`) to import from the new adapter-layer locations.
- Updated `test/api/v2/backend/test_trigger_services.py` imports.
- Deleted `vultron/api/v2/backend/trigger_services/` entirely (5 Python files).
- `vultron/api/v2/` now contains only `data/actor_io.py` (pending VCR-014)
  and two `__init__.py` stubs.

**Result**: 996 tests pass, no regressions.

**Notes**: The old `_helpers.py` re-export shim (which re-exported core helpers
like `add_activity_to_outbox`, `resolve_actor` etc.) is now gone entirely.
All callers already imported those from `vultron.core.use_cases.triggers._helpers`
directly (confirmed by test suite passing).

---

### TECHDEBT-29 — Profile endpoint returns inbox/outbox as URL strings (2026-03-23)

**Task**: Clarify and enforce that `GET /actors/{actor_id}/profile` returns
inbox and outbox as URL strings, not embedded OrderedCollection objects.

**What was done**:

- Updated `specs/agentic-readiness.yaml` AR-10-001 to require `inbox` and
  `outbox` as string URL links (not embedded collection objects); updated
  the verification section accordingly.
- Modified `vultron/adapters/driving/fastapi/routers/actors.py`
  `get_actor_profile()`: removed `response_model=as_Actor`; profile is now
  built via `model_dump(by_alias=True, exclude_none=True)` then inbox/outbox
  overridden with their `.as_id` string URLs.
- Updated `test/api/v2/routers/test_actors.py` to assert `inbox` and `outbox`
  are `str` instances (not dicts).

**Result**: 996 tests pass, no regressions. Spec and test now agree.

**Notes**: The existing `as_Actor.inbox` default_factory creates collections
with random UUIDs as IDs (the `set_collections` validator only fires when
`inbox is None`). Fixing the collection IDs to be `{actor_id}/inbox`-style
URLs is a separate concern tracked as a future improvement.
