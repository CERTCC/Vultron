---
source: NOTES-domain-model-separation--dry-and-post-p75-2
timestamp: '2026-09-17T17:22:00.984009+00:00'
title: DRY core domain models and post-P75-2 architecture findings
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,c) delivered; VultronObject base exists; handlers removed, semantic_registry replaced use_case_map.py, dispatcher moved to core/ports/dispatcher.py
**Superseded by:** vultron/core/models/base.py; vultron/core/ports/dispatcher.py; vultron/semantic_registry/

---

## DRY Core Domain Models

`vultron/core/models/vultron_types.py` and `vultron/core/models/events.py`
have overlapping responsibilities. Both define domain model classes that
inherit directly from `pydantic.BaseModel`. There is no shared base class
capturing common fields (identity, timestamps, labels).

**Target design**: Define a `VultronObject` base class in core that captures
all fields common across domain objects (e.g., `id`, `name`, `created_at`,
`updated_at`). `VultronEvent` should inherit from `VultronObject`. Other
domain model classes (Case, Report, Participant) should also inherit from
`VultronObject` rather than directly from `BaseModel`.

This mirrors the wire-layer class hierarchy (`as_Base` → `as_Object` →
`as_Activity` → ...) but at the domain level, free of ActivityStreams
vocabulary constraints.

Benefits:

- Eliminates repetitive `id: str`, `name: str` etc. fields scattered across
  models.
- Provides a single place to add cross-cutting concerns (validation, repr).
- Makes the domain hierarchy explicitly parallel to the wire hierarchy.

**See**: `notes/codebase-structure.md` "Core Object Modules" for the
related file-splitting recommendation.

---

## Post-P75-2 Architecture Findings

After P75-2 (handler extraction to `core/use_cases/`), several
implementation details became clear:

### Handler Layer Is Vestigial

`vultron/api/v2/backend/handlers/` now contains thin 2–3-line delegate
functions. Their sole remaining purpose is to call use-case functions and
apply the `@verify_semantics` decorator. This layer can be eliminated by
mapping `SEMANTICS_HANDLERS` directly to use-case callables and moving
semantic verification into the dispatcher.

### SEMANTICS_HANDLERS Belongs in Core

`SEMANTICS_HANDLERS` maps `MessageSemantics` values (domain concepts) to
use-case callables (domain code). This mapping is domain knowledge, not
adapter configuration, and belongs in `core/use_cases/use_case_map.py`.

### ActivityDispatcher as Driving Port

The `ActivityDispatcher` Protocol in `vultron/types.py` should be moved
to `core/ports/dispatcher.py` alongside `DataLayer`. This makes the inbound
dispatch interface explicit and injectable (for testing). The concrete
implementation moves to core (or a thin driving adapter).

### Pattern Naming Inconsistency

`ActivityPattern` instances registered in `SEMANTIC_REGISTRY` use names like
`CreateReport`, `EngageCase` — identical to
Activity and Event class names. Adding a `Pattern` suffix (e.g.,
`CreateReportPattern`, `EngageCasePattern`) prevents naming collisions and
clarifies purpose.

**See**: `notes/use-case-behavior-trees.md` for the standardized `UseCase`
protocol proposal.

---
