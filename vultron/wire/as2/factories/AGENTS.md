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

## Completeness Is the Factory's (MUST)

The blob a factory produces is delivered byte for byte and recorded as the
ledger `payloadSnapshot` unchanged (VM-08-003); nothing downstream expands,
collapses, or patches it. So:

- A case-scoped factory MUST complete `context` with the case URI —
  `**with_case_context(kwargs, target)` (`_context.py`) — never an emit node.
- A case handed in as `target` MUST go out as its URI (the recipient holds the
  case, AKM-02-002/003) or as the `Invite`'s selective-disclosure stub — never
  the full object. Pass `target=case_target_ref(target)`.
- An initiating activity's `object` MUST be the full inline object
  (AKM-03-001); the outbox refuses a bare reference, it no longer repairs one.

Ratchet: `test/adapters/driven/trigger_activity_adapter/test_sealed_body_audit.py`
exercises every trigger-port method against these three rules.
