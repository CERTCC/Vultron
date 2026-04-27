# Activity Factory Functions Specification

## Overview

Requirements governing the factory function API for constructing outbound
Vultron protocol activities. Factory functions replace direct instantiation of
Vultron activity subclasses as the public construction API and are the sole
import point for activity construction outside the wire vocabulary layer.

**Source**: `plan/IDEAS.md` IDEA-26042001, `notes/activity-factories.md`

**Cross-references**: `architecture.md` ARCH-03-001 (wire boundary),
`vocabulary-model.md` VM-01 through VM-05 (vocabulary registration),
`code-style.md` CS-05-001 (layer separation), `error-handling.md`

---

## Purpose and Scope

- `AF-01-001` (MUST) Factory functions MUST be the sole public construction API
  for outbound Vultron protocol activities
  - All code outside `vultron/wire/as2/vocab/activities/` and
    `vultron/wire/as2/factories/` MUST construct activities by calling factory
    functions, not by directly instantiating Vultron activity subclasses
  - AF-01-001 implements the import boundary defined in AF-05-001
- `AF-01-002` (MUST) Factory functions MUST return plain AS2 base types
  (e.g. `as_Offer`, `as_Accept`, `as_Create`) rather than Vultron activity
  subclasses
  - Callers receive the simplest type that correctly describes the message,
    removing the need to understand Vultron's inheritance hierarchy
- `AF-01-003` (MUST) Factory function signatures MUST declare explicit,
  domain-typed parameters for all protocol-significant fields
  - Example: `rm_submit_report_activity(report: VulnerabilityReport,
    to: as_Actor, ...) -> as_Offer` expresses the protocol constraint as a
    type annotation, not as a subclass field override
- `AF-01-004` (SHOULD) Factory functions SHOULD accept `**kwargs` for
  optional AS2 fields that are not protocol-significant, forwarding them to
  the underlying AS2 constructor
  - This allows callers to set fields such as `published`, `summary`, or
    `context` without requiring separate factory overloads

## Module Structure

- `AF-02-001` (MUST) All factory functions MUST live in the
  `vultron/wire/as2/factories/` package — a sibling of `vultron/wire/as2/vocab/`
  - This placement makes the import boundary rule AF-05-001 easy to express
    and verify: valid imports come from `as2/factories/`, violations come from
    `as2/vocab/activities/`
- `AF-02-002` (MUST) The `factories/` package MUST be organized into one
  module per protocol domain, mirroring the existing `vocab/activities/`
  modules:

  | Factory module | Source activity module |
  |---|---|
  | `factories/report.py` | `vocab/activities/report.py` |
  | `factories/case.py` | `vocab/activities/case.py` |
  | `factories/embargo.py` | `vocab/activities/embargo.py` |
  | `factories/case_participant.py` | `vocab/activities/case_participant.py` |
  | `factories/actor.py` | `vocab/activities/actor.py` |
  | `factories/sync.py` | `vocab/activities/sync.py` |

- `AF-02-003` (MUST) `factories/__init__.py` MUST re-export every factory
  function from all domain modules so callers can use a single
  `from vultron.wire.as2.factories import ...` import
- `AF-02-004` (MUST) `VultronActivityConstructionError` MUST be defined in
  `vultron/wire/as2/factories/errors.py` and imported into `factories/__init__.py`

## Function Naming

- `AF-03-001` (MUST) Factory function names MUST be the snake_case equivalent
  of the corresponding Vultron activity class name
  - `RmSubmitReportActivity` → `rm_submit_report_activity()`
  - `EmProposeEmbargoActivity` → `em_propose_embargo_activity()`
  - `RmAcceptInviteToCaseActivity` → `rm_accept_invite_to_case_activity()`
  - This 1-to-1 naming ensures that migration diffs are minimal and
    searchable, and that the protocol meaning encoded in the class name is
    preserved

## Error Handling

- `AF-04-001` (MUST) Every factory function MUST wrap Pydantic
  `ValidationError` in `VultronActivityConstructionError`
  - The original `ValidationError` MUST be chained as `__cause__` so that
    the original validation details remain accessible
  - `VultronActivityConstructionError` MUST inherit from `VultronError`
    (`vultron/errors.py`) so it fits the project's exception hierarchy
    (see `error-handling.md`)
  - Error messages MUST NOT expose the name of the private internal class;
    they SHOULD name the factory function instead
- `AF-04-002` (MUST) `VultronActivityConstructionError` MUST be defined in
  `vultron/wire/as2/factories/errors.py` and re-exported from
  `vultron/wire/as2/factories/__init__.py`
- `AF-04-003` (SHOULD) Factory functions SHOULD log a `WARNING` before raising
  `VultronActivityConstructionError` so that construction failures are
  observable without requiring callers to catch the exception

## Internal Vocabulary Classes

- `AF-05-001` (MUST) Vultron activity subclasses in
  `vultron/wire/as2/vocab/activities/` MUST NOT be imported by any module
  outside that package or `vultron/wire/as2/factories/`
  - The only permitted use of the internal classes is as Pydantic validators
    inside the factory functions that correspond to them
  - This rule is enforced by an automated import-boundary test
    (see AF-06-001)
- `AF-05-002` (MUST) Inside each factory function the corresponding internal
  class MUST be instantiated first; the result is returned typed as the plain
  AS2 base type
  - This preserves Pydantic runtime field validation while hiding the
    subclass from callers
  - Example:

    ```python
    def rm_submit_report_activity(
        report: VulnerabilityReport,
        to: as_Actor | str,
        **kwargs,
    ) -> as_Offer:
        try:
            return RmSubmitReportActivity(
                object_=report, to=[to], **kwargs
            )
        except ValidationError as exc:
            raise VultronActivityConstructionError(
                "rm_submit_report_activity: invalid arguments"
            ) from exc
    ```

- `AF-05-003` (SHOULD) Internal Vultron activity classes SHOULD be prefixed
  with `_` or otherwise marked as private once factory functions exist for
  them, to signal that they are implementation details

## Import Boundary Enforcement

- `AF-06-001` (MUST) A pytest test in `test/architecture/` MUST verify that
  no Python source file outside `vultron/wire/as2/vocab/activities/` and
  `vultron/wire/as2/factories/` contains an import from
  `vultron.wire.as2.vocab.activities`
  - Exceptions: `__init__.py` files that use `pkgutil` / `importlib` for
    dynamic discovery are exempt (they do not name individual classes)
  - The test MUST produce a clear failure message listing the offending files
    and the violating import lines
- `AF-06-002` (MUST) The `test/architecture/` package MUST be a proper pytest
  package (`__init__.py` present) so that future architectural enforcement
  tests can be added alongside it

## TypeAlias Cleanup

- `AF-07-001` (MUST) The unused `OfferRef` TypeAlias in
  `vocab/activities/report.py` MUST be removed
- `AF-07-002` (MUST) The unused `RmInviteToCaseRef` TypeAlias in
  `vocab/activities/case.py` MUST be removed
- `AF-07-003` (SHOULD) The `EmProposeEmbargoRef` TypeAlias in
  `vocab/activities/embargo.py` SHOULD be renamed to `_EmProposeEmbargoRef`
  (private prefix) since it is used only within `embargo.py` and is not
  intended as a public export

## Migration

- `AF-08-001` (MUST) All call sites outside `vultron/wire/as2/vocab/activities/`
  and `vultron/wire/as2/factories/` that directly instantiate a Vultron
  activity subclass MUST be migrated to use the corresponding factory function
  - Affected call sites include demo scripts, trigger use-case modules, and
    tests
  - Migration MUST be completed before the Vultron activity subclasses are
    made private (see AF-05-003)
- `AF-08-002` (SHOULD) Migration of `from_core()` call sites in
  `vultron/core/use_cases/` to use driven adapter translation instead of
  calling wire-layer methods directly is a **separate tracked task** and MUST
  NOT be conflated with factory function migration
  - See the architecture violation note in `notes/activity-factories.md`

## Verification

### AF-01 through AF-05 Verification

- Unit test: each factory function in `factories/report.py`,
  `factories/case.py`, `factories/embargo.py`, `factories/case_participant.py`,
  `factories/actor.py`, and `factories/sync.py` returns an instance of the
  correct plain AS2 base type (not the internal Vultron subclass)
- Unit test: passing a wrong-typed argument to a factory function raises
  `VultronActivityConstructionError` (not `ValidationError`)
- Unit test: `VultronActivityConstructionError.__cause__` is the original
  `ValidationError`
- Unit test: factories return objects that round-trip through
  `to_json()` / `model_validate_json()` cleanly

### AF-06-001 Verification

- Architecture test in `test/architecture/test_activity_factory_imports.py`:
  scan all `.py` files outside `vultron/wire/as2/vocab/activities/` and
  `vultron/wire/as2/factories/`; assert none contain an import from
  `vultron.wire.as2.vocab.activities`
- Test MUST fail before migration is complete and pass after

### AF-07 Verification

- Unit test: `from vultron.wire.as2.vocab.activities.report import OfferRef`
  raises `ImportError` (alias has been removed)
- Unit test: `from vultron.wire.as2.vocab.activities.case import
  RmInviteToCaseRef` raises `ImportError`

## Related

- **Factory implementations**: `vultron/wire/as2/factories/`
- **Internal classes**: `vultron/wire/as2/vocab/activities/`
- **Error class**: `vultron/wire/as2/factories/errors.py`
- **Boundary test**: `test/architecture/test_activity_factory_imports.py`
- **Notes**: `notes/activity-factories.md`
- **Wire vocabulary spec**: `specs/vocabulary-model.yaml`
- **Architecture spec**: `specs/architecture.yaml` (ARCH-03-001)
- **Code style**: `specs/code-style.yaml` (CS-05-001)
