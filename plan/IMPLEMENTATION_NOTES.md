## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

### 2026-03-11 — Refresh #24 findings

**P65 fully complete**: All tasks P65-1 through P65-7 are confirmed complete by
code inspection. V-01 through V-23 are all resolved. See `IMPLEMENTATION_HISTORY.md`
for details.

**`notes/architecture-review.md` is stale**: The status block and per-violation
markers still show V-03-R, V-15–19, and V-22–23 as open or partial. These were
resolved by P65-4, P65-6b, and P65-7 respectively. ARCH-DOCS-1 task added.

**New violation V-24**: `vultron/wire/as2/vocab/examples/_base.py` imports
`DataLayer` from `vultron.api.v2.datalayer.abc` at module scope, and also
imports `Record` and `get_datalayer` from `api/v2/datalayer/` inside
`initialize_examples()`. This makes the wire layer dependent on the adapter
layer — a Rule 1 violation. Captured in TECHDEBT-13b.

**Residual V-23**: `test/core/behaviors/report/test_policy.py` still imports
`VulnerabilityReport` from `vultron.wire.as2.vocab.objects.vulnerability_report`.
Tests pass (duck-typing), but the import violates the rule that core tests must
not use wire-layer types as fixtures. Captured in TECHDEBT-13a.

**TYPE_CHECKING imports in top-level modules**: `vultron/types.py` and
`vultron/behavior_dispatcher.py` both have `TYPE_CHECKING` guards importing
`DataLayer` from `vultron.api.v2.datalayer.abc` (the backward-compat shim).
These should import from `vultron.core.ports.activity_store` directly.
Captured in TECHDEBT-13c.

**`api/v2` → `core/use_cases/` migration (PRIORITY-75)**: The 38 handlers
(2223 lines) in `api/v2/backend/handlers/` and the trigger services (1188 lines)
in `api/v2/backend/trigger_services/` contain domain logic that belongs in
`core/use_cases/`. The `core/use_cases/__init__.py` stub docstring already
describes the intent: "Incoming port: domain use-case callables." Migration
requires domain event types (`VultronEvent`) first (P75-1), then handler
extraction (P75-2), then trigger service extraction (P75-3), then updating
driving adapter stubs to call use cases directly (P75-4).

**api/v1 is already architecturally compliant**: All v1 routers return
`vocab_examples.*` results with no business logic. They are already thin HTTP
adapters over `wire/as2/vocab/examples/`. The only decision needed is whether
to keep, merge, or deprecate (P75-5).

**P70 needs P70-4 and P70-5**: Moving TinyDB from `api/v2/datalayer/tinydb.py`
to `adapters/driven/activity_store.py` (P70-4) and removing the backward-compat
shims (P70-5) were missing from the plan. Added in refresh #24.

**`vultron_types.py` split**: `vultron/core/models/vultron_types.py` bundles
11 domain classes in 273 lines. `notes/codebase-structure.md` recommends
splitting into per-type modules (like `wire/as2/vocab/objects/`). Low-priority
organizational improvement captured as TECHDEBT-14.

**`use_cases` directory**: `vultron/core/use_cases/__init__.py` exists with a
stub docstring but contains no implementations. Driving adapter stubs
(`http_inbox.py`, `mcp_server.py`) reference `core/use_cases/` as the
future home for use-case callables. No actionable task yet — this will come
with the hexagonal architecture maturing (PRIORITY 70+).

## Renamed activity_store

`core/ports/activity_store.py` was renamed to `core/ports/datalayer.py` to  
reflect the broader scope of the port.

`adapters/driven/activity_store.py` was renamed to 
`adapters/driven/datalayer-tinydb.py` to reflect the specific  
implementation and avoid confusion with the port. (Eventually when we get to 
having a mongo-db implementation we will want to make 
`adapters/driven/datalayer` into a package with `tinydb.py` and `mongodb.py` 
as modules.)

