# Codebase Structure Notes — Historical / Completed Sections

These sections were stripped from `notes/codebase-structure.md` during the
April 2026 notes refactoring. They describe completed or fully-superseded
implementation tasks and are kept here only for historical reference.

---

## API Layer Architecture (Historical — Completed in VCR Batch B / P65)

> **Note**: This section is retained as historical context. The proposed
> reorganization was completed in VCR Batch B (March 2026). `vultron/api/v2/`
> no longer exists. All code now lives under
> `vultron/adapters/driving/fastapi/` (inbox, outbox, routers) and
> `vultron/core/use_cases/` (business logic).

The old codebase treated `vultron/api/v1/` and `vultron/api/v2/` as version
numbers, but they were actually more like **distinct layers**:

| Layer | Old location | Current canonical location |
|---|---|---|
| ActivityPub layer | `vultron/api/v2/routers/actors.py` | `vultron/adapters/driving/fastapi/routers/actors.py` |
| Backend services layer | `vultron/api/v2/backend/` | `vultron/core/use_cases/` + `vultron/adapters/driving/fastapi/` |
| Examples layer | `vultron/api/v1/` | Removed |

---

## Use-Case Module Structure (Completed — REORG-1)

The `vultron/core/use_cases/` package is organized as follows:

- `received/` — inbound message handler use cases (8 submodules: `report.py`,
  `case.py`, `embargo.py`, `actor.py`, `note.py`, `participant.py`,
  `status.py`, `unknown.py`)
- `triggers/` — actor-initiated trigger use cases (`embargo.py`, `report.py`,
  `case.py`, `_helpers.py`)
- `query/` — query use cases (`action_rules.py`)
- `_helpers.py` — shared helpers used by `received/` and `triggers/`
- `use_case_map.py` — `USE_CASE_MAP` routing table (`MessageSemantics` →
  use-case class)

**See**: `vultron/core/use_cases/README.md` and `plan/IMPLEMENTATION_HISTORY.md`
Phase REORG-1 (completed 2026-03-30).

---

## Vocabulary Examples Module Structure (Completed)

`vultron/wire/as2/vocab/examples/` contains vocabulary example submodules
organized by topic: `_base.py`, `actor.py`, `case.py`, `embargo.py`, `note.py`,
`participant.py`, `report.py`, `status.py`. The top-level `vocab_examples.py`
in that package re-exports all public names.

The old `vultron/as_vocab/` package was relocated to `vultron/wire/as2/vocab/`
as part of P60-1. Import directly from `vultron.wire.as2.vocab.examples`.

**See**: `plan/IMPLEMENTATION_PLAN.md` Phase TECHDEBT-5, TECHDEBT-6, and P60-1
(all completed).

---

## Technical Debt: Deprecated HTTP Status Constant (TECHDEBT-12, ✅ resolved)

The trigger_services files that contained `HTTP_422_UNPROCESSABLE_ENTITY`
usages (`vultron/api/v2/backend/trigger_services/`) were removed in VCR Batch
D (2026-03-19). The trigger adapter code is now in
`vultron/adapters/driving/fastapi/_trigger_adapter.py` and
`vultron/adapters/driving/fastapi/errors.py`, which use
`HTTP_422_UNPROCESSABLE_CONTENT`.

---

## Resolved: Outbox Delivery (OX-1.0–1.4, ✅ completed 2026-03-25)

Outbox delivery was implemented in OX-1.0 through OX-1.4 (March 2026).
The `ActivityEmitter` port stub, delivery queue, and outbox delivery loop
are now in place. `actor_io.py` (the old placeholder) was deleted in
VCR-014.

**Reference**: `specs/outbox.yaml`; `plan/IMPLEMENTATION_HISTORY.md` Phase
OX-1.0–1.4 and VCR-014.

---

## Resolved: `app.py` Root Logger Side Effect

`vultron/adapters/driving/fastapi/app.py` (formerly `vultron/api/v2/app.py`)
previously called `logging.getLogger().setLevel(logging.DEBUG)` at module
import time, causing test isolation problems.

**Status**: Fixed in BUGFIX-1.1. Root logger configuration is now inside the
`lifespan` context manager so importing the module in tests does not mutate
the root logger.

---

## Trigger Services Package (✅ completed in VCR Batch D / P75, 2026-03-19)

The `vultron/api/v2/backend/trigger_services/` package has been fully
superseded and removed. The content was relocated as follows:

| Old file | New location |
|----------|-------------|
| `_helpers.py` | `vultron/adapters/driving/fastapi/_trigger_adapter.py` and `vultron/adapters/driving/fastapi/errors.py` |
| `_models.py` | `vultron/adapters/driving/fastapi/trigger_models.py` |
| `case.py` | `vultron/core/use_cases/triggers/case.py` (logic) + `vultron/adapters/driving/fastapi/routers/trigger_case.py` (HTTP) |
| `embargo.py` | `vultron/core/use_cases/triggers/embargo.py` (logic) + `vultron/adapters/driving/fastapi/routers/trigger_embargo.py` (HTTP) |
| `report.py` | `vultron/core/use_cases/triggers/report.py` (logic) + `vultron/adapters/driving/fastapi/routers/trigger_report.py` (HTTP) |

`vultron/api/v2/` has been fully removed (VCR-014 deleted the last file,
`data/actor_io.py`, in 2026-03-25).

---
