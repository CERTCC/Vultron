---
title: "Activity Factories — Design Rules and Inventory"
status: active
tags: [factories, wire, outbound-activities, migration, as2]
description: >
  Design decisions, full factory inventory, migration guide, and testing
  patterns for the factory-function layer that wraps Vultron's internal
  ActivityStreams subclasses. Operating rules live in
  vultron/wire/as2/factories/AGENTS.md.
related_specs:
  - specs/activity-factories.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/architecture-hexagonal.md
relevant_packages:
  - vultron/wire/as2/factories
  - vultron/wire/as2/vocab/activities
---

# Activity Factories — Design Rules and Inventory

Operating rules summary: `vultron/wire/as2/factories/AGENTS.md`.
Spec: `specs/activity-factories.yaml` (AF-01 through AF-08).

## Design Decisions

| Question | Decision | Rationale |
|---|---|---|
| Replace subclasses outright or additive? | Additive first: factories alongside existing classes, then migrate call sites, then make classes private | Non-breaking; lets us validate the pattern before removing the old API. |
| Which classes become factory functions? | All Vultron activity subclasses across all domain modules | Partial migration would leave an inconsistent API. |
| Return type of factory functions? | Plain AS2 base type (for example, `as_Offer`, not `RmSubmitReportActivity`) | Callers do not need to understand Vultron's inheritance hierarchy. |
| Module location? | `vultron/wire/as2/factories/` — sibling of `vocab/` | Makes the import boundary rule easy to state and enforce. |
| One module or split by domain? | One module per domain (`report.py`, `case.py`, `embargo.py`, `case_participant.py`, `actor.py`, `sync.py`) | Mirrors the existing `vocab/activities/` split and keeps files small. |
| Internal classes kept or deleted? | Kept as private implementation details inside factory modules | They provide Pydantic runtime validation for free. |
| Error handling? | Catch `ValidationError`, raise `VultronActivityConstructionError` (chains `__cause__`) | Keeps internal class names out of public error messages. |
| Import boundary enforcement? | pytest `test/architecture/test_activity_factory_imports.py` + AGENTS guidance | Lightweight, CI-enforced boundary rule. |
| TypeAlias cleanup? | Remove unused `OfferRef` and `RmInviteToCaseRef`; rename `EmProposeEmbargoRef` to `_EmProposeEmbargoRef` | Reduces public API surface. |
| `from_core()` on `VultronAS2Activity`? | Keep; it is a separate concern | Factories build from primitives; `from_core()` converts an existing domain object. |
| Architecture violation in `sync.py`? | Track separately | `vultron/core/use_cases/*/sync.py` calling `from_core()` is a different layer violation. |

## Key Patterns

### Factory Function Shape

```python
# vultron/wire/as2/factories/report.py

from pydantic import ValidationError

from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.report import RmSubmitReportActivity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_report import VulnerabilityReport


def rm_submit_report_activity(
    report: VulnerabilityReport,
    to: as_Actor | str,
    **kwargs,
) -> as_Offer:
    """Build an Offer(VulnerabilityReport) — the RS message."""
    try:
        return RmSubmitReportActivity(object_=report, to=[to], **kwargs)
    except ValidationError as exc:
        raise VultronActivityConstructionError(
            "rm_submit_report_activity: invalid arguments"
        ) from exc
```

### Error Class

```python
# vultron/wire/as2/factories/errors.py

from vultron.errors import VultronError


class VultronActivityConstructionError(VultronError):
    """Raised when a factory function cannot construct the requested activity.

    Wraps a Pydantic ValidationError as __cause__ so that callers can
    inspect the original validation details if needed.
    """
```

### `__init__.py` Re-export Pattern

```python
# vultron/wire/as2/factories/__init__.py

from vultron.wire.as2.factories.errors import (
    VultronActivityConstructionError,
)
from vultron.wire.as2.factories.report import (
    rm_close_report_activity,
    rm_create_report_activity,
    rm_invalidate_report_activity,
    rm_read_report_activity,
    rm_submit_report_activity,
    rm_validate_report_activity,
)

__all__ = [
    "VultronActivityConstructionError",
    "rm_submit_report_activity",
    # ...
]
```

## Migration Guide

### Call-site Pattern: Before and After

```python
# BEFORE (direct class instantiation — violates AF-01-001 after migration)
from vultron.wire.as2.vocab.activities.report import RmSubmitReportActivity

report_offer = RmSubmitReportActivity(
    object_=report,
    to=[alice_id],
)

# AFTER (factory function — correct)
from vultron.wire.as2.factories import rm_submit_report_activity

report_offer = rm_submit_report_activity(report=report, to=alice_id)
```

```python
# BEFORE
from vultron.wire.as2.vocab.activities.case import RmAcceptInviteToCaseActivity

accept = RmAcceptInviteToCaseActivity(actor=actor.id_, object_=invite)

# AFTER
from vultron.wire.as2.factories import rm_accept_invite_to_case_activity

accept = rm_accept_invite_to_case_activity(actor=actor.id_, invite=invite)
```

```python
# BEFORE (embargo proposal)
from vultron.wire.as2.vocab.activities.embargo import EmProposeEmbargoActivity

proposal = EmProposeEmbargoActivity(object_=embargo_event, context=case_ref)

# AFTER
from vultron.wire.as2.factories import em_propose_embargo_activity

proposal = em_propose_embargo_activity(embargo=embargo_event, context=case_ref)
```

### Accept/Reject with `model_validator` Logic

Classes like `RmAcceptInviteToCaseActivity` have a `model_validator`
that auto-sets `in_reply_to` from the invite's `id_`. The factory
function absorbs this:

```python
# factories/case.py
def rm_accept_invite_to_case_activity(
    invite: as_Invite,
    actor: str | None = None,
    **kwargs,
) -> as_Accept:
    """Build Accept(Invite) — the RV message when a case already exists."""
    try:
        return RmAcceptInviteToCaseActivity(
            actor=actor,
            object_=invite,
            **kwargs,
        )
    except ValidationError as exc:
        raise VultronActivityConstructionError(
            "rm_accept_invite_to_case_activity: invalid arguments"
        ) from exc
```

The `model_validator` on the internal class still fires — no need to
duplicate the logic in the factory.

## Full Factory Inventory

### `factories/report.py`

| Factory function | Return type | Internal class |
|---|---|---|
| `rm_create_report_activity` | `as_Create` | `RmCreateReportActivity` |
| `rm_submit_report_activity` | `as_Offer` | `RmSubmitReportActivity` |
| `rm_read_report_activity` | `as_Read` | `RmReadReportActivity` |
| `rm_validate_report_activity` | `as_Accept` | `RmValidateReportActivity` |
| `rm_invalidate_report_activity` | `as_TentativeReject` | `RmInvalidateReportActivity` |
| `rm_close_report_activity` | `as_Reject` | `RmCloseReportActivity` |

### `factories/case.py`

| Factory function | Return type | Internal class |
|---|---|---|
| `add_report_to_case_activity` | `as_Add` | `AddReportToCaseActivity` |
| `add_status_to_case_activity` | `as_Add` | `AddStatusToCaseActivity` |
| `create_case_activity` | `as_Create` | `CreateCaseActivity` |
| `create_case_status_activity` | `as_Create` | `CreateCaseStatusActivity` |
| `add_note_to_case_activity` | `as_Add` | `AddNoteToCaseActivity` |
| `update_case_activity` | `as_Update` | `UpdateCaseActivity` |
| `rm_engage_case_activity` | `as_Join` | `RmEngageCaseActivity` |
| `rm_defer_case_activity` | `as_Ignore` | `RmDeferCaseActivity` |
| `rm_close_case_activity` | `as_Leave` | `RmCloseCaseActivity` |
| `offer_case_ownership_transfer_activity` | `as_Offer` | `OfferCaseOwnershipTransferActivity` |
| `accept_case_ownership_transfer_activity` | `as_Accept` | `AcceptCaseOwnershipTransferActivity` |
| `reject_case_ownership_transfer_activity` | `as_Reject` | `RejectCaseOwnershipTransferActivity` |
| `rm_invite_to_case_activity` | `as_Invite` | `RmInviteToCaseActivity` |
| `rm_accept_invite_to_case_activity` | `as_Accept` | `RmAcceptInviteToCaseActivity` |
| `rm_reject_invite_to_case_activity` | `as_Reject` | `RmRejectInviteToCaseActivity` |
| `announce_vulnerability_case_activity` | `as_Announce` | `AnnounceVulnerabilityCaseActivity` |

### `factories/embargo.py`

| Factory function | Return type | Internal class |
|---|---|---|
| `em_propose_embargo_activity` | `as_Invite` | `EmProposeEmbargoActivity` |
| `em_accept_embargo_activity` | `as_Accept` | `EmAcceptEmbargoActivity` |
| `em_reject_embargo_activity` | `as_Reject` | `EmRejectEmbargoActivity` |
| `choose_preferred_embargo_activity` | `as_Question` | `ChoosePreferredEmbargoActivity` |
| `activate_embargo_activity` | `as_Add` | `ActivateEmbargoActivity` |
| `add_embargo_to_case_activity` | `as_Add` | `AddEmbargoToCaseActivity` |
| `announce_embargo_activity` | `as_Announce` | `AnnounceEmbargoActivity` |
| `remove_embargo_from_case_activity` | `as_Remove` | `RemoveEmbargoFromCaseActivity` |

### `factories/case_participant.py`

| Factory function | Return type | Internal class |
|---|---|---|
| `create_participant_activity` | `as_Create` | `CreateParticipantActivity` |
| `create_status_for_participant_activity` | `as_Create` | `CreateStatusForParticipantActivity` |
| `add_status_to_participant_activity` | `as_Add` | `AddStatusToParticipantActivity` |
| `add_participant_to_case_activity` | `as_Add` | `AddParticipantToCaseActivity` |
| `remove_participant_from_case_activity` | `as_Remove` | `RemoveParticipantFromCaseActivity` |

### `factories/actor.py`

| Factory function | Return type | Internal class |
|---|---|---|
| `recommend_actor_activity` | `as_Offer` | `RecommendActorActivity` |
| `accept_actor_recommendation_activity` | `as_Accept` | `AcceptActorRecommendationActivity` |
| `reject_actor_recommendation_activity` | `as_Reject` | `RejectActorRecommendationActivity` |

### `factories/sync.py`

| Factory function | Return type | Internal class |
|---|---|---|
| `announce_log_entry_activity` | `as_Announce` | `AnnounceLogEntryActivity` |
| `reject_log_entry_activity` | `as_Reject` | `RejectLogEntryActivity` |

## Anti-Pattern: `model_dump` + `model_validate` Instead of `from_core()`

When converting a core domain object to its wire counterpart in adapter
code, always use `wire_cls.from_core(core_obj)`. **Do NOT use**
`wire_cls.model_validate(core_obj.model_dump(by_alias=True, serialize_as_any=True))`.

The `model_dump + model_validate` pattern breaks silently when a wire class
has field types that differ from the core class. Example: `VulnerabilityCase.case_activity`
is `list[str]` (URI strings) in core, but `as_VulnerabilityCase.case_activity`
is `list[as_Activity]`. Pydantic raises `ValidationError` when validating URI
strings as `as_Activity` objects — with no indication that the wrong conversion
path was used.

`from_core()` is defined on `VultronAS2Object` (and overridden on specific wire
classes) and handles all field-type differences via `_field_map`,
`_strip_core_context`, and custom conversion logic. It is the canonical
core→wire conversion path.

Source: ISSUE-1503 — discovered during `datalayer_sqlite` adapter refactoring.

## Architecture Violation: `from_core()` in Core Use Cases

`vultron/core/use_cases/received/sync.py` and
`vultron/core/use_cases/triggers/sync.py` call `from_core()` on wire
objects (`CaseLedgerEntry.from_core(entry)`, `WireCaseLedgerEntry.from_core(entry)`).
This violates the hexagonal architecture rule that core modules must not
import from the wire layer.

The correct fix, tracked separately, is to move the domain->wire
translation into a driven adapter or outbox port adapter so that core use
cases hand domain objects to an adapter and receive wire-format objects
back, without directly calling wire-layer methods.

This fix MUST NOT be included in the factory function migration — the
scopes are separate.

## Testing Patterns

```python
# test/wire/as2/factories/test_report_factories.py

from vultron.wire.as2.factories import rm_submit_report_activity
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer


def test_rm_submit_report_returns_offer(sample_report, sample_actor):
    result = rm_submit_report_activity(report=sample_report, to=sample_actor)
    assert isinstance(result, as_Offer)
    assert result.object_ == sample_report


def test_rm_submit_report_wrong_type_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_submit_report_activity(report="not-a-report", to="actor")
    assert exc_info.value.__cause__ is not None
```

```python
# test/architecture/test_activity_factory_imports.py

import ast
from pathlib import Path

VULTRON_ROOT = Path("vultron")
ALLOWED = {
    VULTRON_ROOT / "wire" / "as2" / "vocab" / "activities",
    VULTRON_ROOT / "wire" / "as2" / "factories",
}
BANNED_PREFIX = "vultron.wire.as2.vocab.activities"


def test_no_direct_activity_class_imports():
    violations = []
    for py_file in VULTRON_ROOT.rglob("*.py"):
        if any(py_file.is_relative_to(a) for a in ALLOWED):
            continue
        if py_file.name == "__init__.py":
            continue
        source = py_file.read_text()
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, "module", "") or ""
                if mod.startswith(BANNED_PREFIX):
                    violations.append(f"{py_file}:{node.lineno}: {mod}")
    assert not violations
```

## Anti-pattern: Projection Logic in the Adapter

**Problem:** An adapter method builds a partial wire object (e.g. `VulnerabilityCaseStub`)
and passes it to a factory function, rather than passing the core domain object and letting
the factory project it.

This pattern appeared in PR #1346, where `_ActorsMixin._build_enriched_case_stub()` was
added to the adapter layer to construct an enriched `VulnerabilityCaseStub` before calling
`rm_invite_to_case_activity()`. The stated reason was that building wire types
(`VulnerabilityCaseStub`, `EmbargoEvent`, `CaseStatus`) in core would violate ARCH-01-001.
That reasoning is wrong — the *factory* is the correct home for this projection, and
factories are already allowed to import both core and wire types.

The concrete bug this caused: `VulnerabilityCase.active_embargo` is `str | None` in the
core model (it stores only the embargo's URI). The adapter read the string, set
`embargo_ref = active_embargo`, and never fetched the `EmbargoEvent` entity from the
DataLayer. The `else` branch that would have built a full `EmbargoEvent(id_=..., end_time=...)`
was unreachable. CM-17-002 requires "ID + `end_time`" in the stub, but only the bare URI
reached the wire. The factory, given a full `VulnerabilityCase`, would naturally call
`self._dl.read(case.active_embargo)` to obtain the entity and extract `end_time` — or the
factory could accept `VulnerabilityCase` + `EmbargoEvent` directly.

**Correct pattern:**

```python
# WRONG — adapter pre-builds partial wire stub
class _ActorsMixin:
    def _build_enriched_case_stub(self, case_id: str) -> VulnerabilityCaseStub:
        case = self._dl.read(case_id)
        ...  # projection logic here, risks being incomplete
        return VulnerabilityCaseStub(id_=case_id, active_embargo=embargo_ref, ...)

    def invite_actor_to_case(self, ..., case_id: str, ...) -> ...:
        target = self._build_enriched_case_stub(case_id)   # ← passes wire stub to factory
        activity = rm_invite_to_case_activity(target=target, ...)

# CORRECT — adapter passes core object; factory projects
class _ActorsMixin:
    def invite_actor_to_case(self, ..., case_id: str, ...) -> ...:
        case = self._dl.read(case_id)                       # ← core object
        activity = rm_invite_to_case_activity(target=case, ...)  # factory projects

# In factories/case.py:
def rm_invite_to_case_activity(
    invitee: CoreActor | as_Actor,
    target: VulnerabilityCase | VulnerabilityCaseStub | str | None = None,
    ...
) -> as_Invite:
    if isinstance(target, VulnerabilityCase):
        target = _project_case_stub(target)   # projection lives here
    ...
```

**Rule (AF-01-005):** When a factory parameter represents a domain entity whose fields
determine how the wire object is enriched, the factory MUST accept the core domain object
and project it internally. See `specs/activity-factories.yaml` AF-01-005.

## Layer and Import Summary

```text
vultron/wire/as2/
├── vocab/
│   └── activities/          <- internal only; imported only by factories/
│       ├── report.py
│       ├── case.py
│       ├── embargo.py
│       ├── case_participant.py
│       ├── actor.py
│       └── sync.py
└── factories/               <- public construction API
    ├── __init__.py          <- re-exports all factory functions
    ├── errors.py            <- VultronActivityConstructionError
    ├── report.py
    ├── case.py
    ├── embargo.py
    ├── case_participant.py
    ├── actor.py
    └── sync.py
```

External code (demos, trigger services, adapters, tests) imports from
`vultron.wire.as2.factories`. The `vocab/activities/` classes are
private implementation details.
