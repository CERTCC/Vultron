---
source: ISSUE-730
timestamp: '2026-06-05T14:36:53.845932+00:00'
title: Migrate Vultron actor types to core/models/
type: implementation
---

## Issue #730 — Migrate Vultron actor types (Person/Organization/Service/Application/Group) to core

Seventh step toward #699. Migrated all five Vultron actor types from the
wire layer into `vultron/core/models/actor.py`. The wire module
(`vultron_actor.py`) is now a thin re-export layer.

### What was implemented

- **`vultron/core/models/actor.py`** (new): `CoreActorCollection`,
  `CoreActor` base with shared actor fields (`inbox`, `outbox`,
  `embargo_policy`, `preferred_username`, etc.), and five concrete
  subtypes (`VultronPerson`, `VultronOrganization`, `VultronService`,
  `VultronApplication`, `VultronGroup`) with `Literal` `type_`
  discriminators. `VultronActorMixin = CoreActor` preserved as a
  backward-compat alias.
- **`vultron/wire/as2/vocab/objects/vultron_actor.py`** (rewritten):
  Thin re-export from core + `VOCABULARY` registration + `*Ref`
  TypeAliases. All downstream importers continue to work unchanged.
- **Adapter routers** (`actors.py`, `datalayer.py`): Widened actor
  type-maps from `as_Actor` to `BaseModel`/`PersistableModel`; removed
  `isinstance(obj, as_Actor)` guards.
- **`extractor.py`**: Extended `AOtype.ACTOR` isinstance check to also
  accept `CoreActor` so nested invite/accept/reject patterns still match
  after migration.
- **`vocab/base/objects/base.py`**: Widened `as_ObjectRef` /
  `as_ObjectRequiredRef` to include `CoreObject` so core actors can be
  embedded in wire `object_` fields without being silently downcast to
  `as_Object`.
- **`test/core/models/test_actor.py`** (new): Unit tests covering core
  actor registration, type literals, `embargo_policy`, and
  `VultronActorMixin` alias.

### Non-obvious fixes

1. **Pattern-matcher fix**: `AOtype.ACTOR` check in `extractor.py` must
   use `isinstance(x, (as_Actor, CoreActor))` because core actors are no
   longer `as_Actor` subclasses. Without this, invite/accept semantic
   detection returned `UNKNOWN`.
2. **`as_ObjectRequiredRef` widening**: Pydantic silently downcoerces a
   `VultronOrganization` (CoreActor, not as_Object) to `as_Object` when
   it is placed in an `as_Invite.object_` field. Widening the TypeAlias
   to include `CoreObject` fixes this without breaking existing behavior.

### Outcome

All five AC from issue #730 satisfied. mypy and pyright pass (0 errors).
3005 tests pass.

PR: [#794](https://github.com/CERTCC/Vultron/pull/794)
