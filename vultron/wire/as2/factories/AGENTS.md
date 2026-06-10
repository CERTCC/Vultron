# Activity Factories — Design Rules

> Full design rationale, factory inventory, migration guide, and testing
> patterns: [`notes/activity-factories.md`](../../../../notes/activity-factories.md)
>
> Spec: `specs/activity-factories.yaml` (AF-01 through AF-08)

## Core Rule (MUST)

All outbound activities MUST be constructed via `vultron.wire.as2.factories`.
Code outside `vultron/wire/as2/vocab/activities/` and
`vultron/wire/as2/factories/` MUST NOT import internal activity subclasses
(e.g., `RmCreateReportActivity`). Boundary enforced by
`test/architecture/test_activity_factory_imports.py`.

## Error Handling

Catch `ValidationError`, raise `VultronActivityConstructionError` (chains
`__cause__`). See `vultron/wire/as2/factories/errors.py`.

## Import Rules

| Source location | Rule |
|---|---|
| `vultron/core/` | MUST NOT import from `factories/` or `vocab/activities/` |
| `vultron/adapters/`, demos, trigger services | MUST use `factories/` |
| Test files | MUST use `factories/`; exceptions only when testing internal class behavior |
