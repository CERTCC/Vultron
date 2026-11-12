# Activity Factories — Design Rules

> Design rules and rationale:
> [`notes/activity-factories.md`](../../../../notes/activity-factories.md)
>
> Spec: `specs/activity-factories.yaml` (AF-01 through AF-09)

## Core Rule (MUST)

All outbound activities MUST be constructed via `vultron.wire.as2.factories`.
Code outside `vultron/wire/as2/vocab/activities/` and
`vultron/wire/as2/factories/` MUST NOT import internal activity subclasses
(e.g., `RmCreateReportActivity`). Boundary enforced by
`test/architecture/test_activity_factory_imports.py`.

## Error Handling

Build the activity with `build_activity(label, cls, at, lambda: {...})`
(`_construct.py`): it logs a WARNING and raises
`VultronActivityConstructionError` (chains `__cause__`) on a `ValidationError`
from the constructor or from any argument expression inside the lambda. Do not
write a factory's own `try/except ValidationError`;
`test/wire/as2/factories/test_construct.py` refuses one.

## Authored at the Act's Instant (MUST)

Every factory takes a required keyword `at: datetime`, the instant of the act
that authors the activity, and `build_activity` sets it as the activity's
`published` and `updated` (ADR-0176). A factory passes `published`/`updated`
nowhere else; the one activity built outside the factories, the trigger
adapter's generic `Add` of a stored object, takes the same `at`.
A trigger-activity or sync port method that builds an activity takes `at` too:
a tree node passes `self._require_act_instant()`, a trigger `self._at`.

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
- An activity that introduces an object (a `Create` or `Add` of a new object, or
  its first delivery) MUST carry it inline (AKM-02-004). When the
  activity class does not refuse a bare id itself (a generic `as_Create`, or a
  class that admits a URI for *received* activities), guard the argument with
  `require_inline` (`_inline.py`).

Ratchets: `test/adapters/driven/trigger_activity_adapter/test_sealed_body_audit.py`
exercises every trigger-port method against these rules;
`test/architecture/test_introduced_objects_inline.py` classifies every factory
by what it introduces, so a new one cannot be added unexamined.
