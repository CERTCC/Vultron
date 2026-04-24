# Activity Factory Functions — Implementation Notes

## Summary

Factory functions replace direct instantiation of Vultron activity subclasses
as the public construction API for outbound protocol messages. The internal
Vultron subclasses (e.g. `RmSubmitReportActivity`) remain as private Pydantic
validators inside the factory modules; they are not part of the public API.

**Spec**: `specs/activity-factories.md` (AF-01 through AF-08)

---

## Design Decisions

| Question | Decision | Rationale |
|---|---|---|
| Replace subclasses outright or additive? | Additive first: factories alongside existing classes, then migrate call sites, then make classes private | Non-breaking; lets us validate the pattern before removing the old API. All migration tasks captured in implementation plan together. |
| Which classes become factory functions? | All Vultron activity subclasses across all domain modules | Achieves the fullest decoupling; partial migration would leave an inconsistent API |
| Return type of factory functions? | Plain AS2 base type (e.g. `as_Offer`, not `RmSubmitReportActivity`) | Simplifies type checking; callers don't need to understand Vultron's inheritance hierarchy |
| Module location? | `vultron/wire/as2/factories/` — sibling of `vocab/` | Makes the import boundary rule easy to state and enforce; separates public construction API from internal vocabulary definitions |
| One module or split by domain? | One module per domain (`report.py`, `case.py`, `embargo.py`, `case_participant.py`, `actor.py`, `sync.py`) | Mirrors existing `vocab/activities/` split; keeps files small |
| Internal classes kept or deleted? | Kept as private implementation details inside factory modules | They provide Pydantic runtime validation for free; hiding them removes the confusion about them being subclass-worthy |
| Error handling? | Catch `ValidationError`, raise `VultronActivityConstructionError` (chains `__cause__`) | Keeps internal class names out of error messages; fits project exception hierarchy |
| Import boundary enforcement? | pytest `test/architecture/test_activity_factory_imports.py` + note in AGENTS.md | Lightweight, runs in CI, gives a clear failure message; `test/architecture/` established as home for future boundary tests |
| TypeAlias cleanup? | Remove unused `OfferRef` and `RmInviteToCaseRef`; rename `EmProposeEmbargoRef` to `_EmProposeEmbargoRef` | They are vestigial or file-internal; removing them reduces public API surface |
| `from_core()` on `VultronAS2Activity`? | Keep; it is a separate concern (domain model → wire round-trip) | Factory functions serve "build from primitives"; `from_core()` serves "convert existing domain object". The `from_core()` calls in core use cases are a separate architecture violation |
| Architecture violation in `sync.py`? | Tracked as a separate implementation task | `vultron/core/use_cases/*/sync.py` calls `from_core()` on wire objects — a layer violation. Out of scope for factory refactor; must be fixed independently via driven adapter |

---

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
    """Build an Offer(VulnerabilityReport) — the RS message.

    Args:
        report: The VulnerabilityReport to submit.
        to: The recipient actor (or actor ID string).
        **kwargs: Optional AS2 fields forwarded to the constructor.

    Returns:
        An ``as_Offer`` whose ``object_`` is the given report.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
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
# ... (all other factory modules)

__all__ = [
    "VultronActivityConstructionError",
    "rm_submit_report_activity",
    # ...
]
```

---

## Migration Guide

### Call-site pattern: before and after

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

### Accept/Reject with model_validator logic

Classes like `RmAcceptInviteToCaseActivity` have a `model_validator` that
auto-sets `in_reply_to` from the invite's `id_`. The factory function absorbs
this:

```python
# factories/case.py
def rm_accept_invite_to_case_activity(
    invite: as_Invite,
    actor: str | None = None,
    **kwargs,
) -> as_Accept:
    """Build Accept(Invite) — the RV message when a case already exists.

    Automatically sets ``in_reply_to`` to the invite's ``id_`` if not
    provided, matching the model_validator in RmAcceptInviteToCaseActivity.
    """
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

---

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

---

## Architecture Violation: `from_core()` in Core Use Cases

`vultron/core/use_cases/received/sync.py` and
`vultron/core/use_cases/triggers/sync.py` call `from_core()` on wire objects
(`CaseLogEntry.from_core(entry)`, `WireCaseLogEntry.from_core(entry)`). This
violates the hexagonal architecture rule that core modules must not import from
the wire layer.

**The correct fix** (tracked separately): move the domain→wire translation into
a driven adapter or outbox port adapter so that core use cases hand domain
objects to an adapter and receive wire-format objects back, without directly
calling wire-layer methods.

This fix MUST NOT be included in the factory function migration — the scopes
are separate. The violation is tracked in `plan/IMPLEMENTATION_PLAN.md`.

---

## Import Rules

| Source location | May import from |
|---|---|
| `vultron/wire/as2/factories/` | `vocab/activities/` (internal classes) + AS2 base types |
| `vultron/core/` | MUST NOT import from `factories/` or `vocab/activities/` |
| `vultron/adapters/` | MAY import from `factories/` |
| Demo scripts, trigger services | MUST use `factories/`; MUST NOT use `vocab/activities/` directly |
| Test files | MUST use `factories/`; exceptions only for tests that specifically test the internal class behavior |

---

## Testing Pattern Examples

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
    assert exc_info.value.__cause__ is not None  # original ValidationError
```

```python
# test/architecture/test_activity_factory_imports.py

import ast
import sys
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
            # skip dynamic-discovery __init__ files
            continue
        source = py_file.read_text()
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, "module", "") or ""
                if mod.startswith(BANNED_PREFIX):
                    violations.append(f"{py_file}:{node.lineno}: {mod}")
    assert not violations, (
        "Direct imports from vultron.wire.as2.vocab.activities are forbidden "
        "outside vocab/activities/ and factories/. Use factory functions "
        "from vultron.wire.as2.factories instead.\n"
        + "\n".join(violations)
    )
```

---

## Layer and Import Summary

```text
vultron/wire/as2/
├── vocab/
│   └── activities/          ← internal only; imported only by factories/
│       ├── report.py
│       ├── case.py
│       ├── embargo.py
│       ├── case_participant.py
│       ├── actor.py
│       └── sync.py
└── factories/               ← public construction API
    ├── __init__.py          ← re-exports all factory functions
    ├── errors.py            ← VultronActivityConstructionError
    ├── report.py
    ├── case.py
    ├── embargo.py
    ├── case_participant.py
    ├── actor.py
    └── sync.py
```

External code (demos, trigger services, adapters, tests) imports from
`vultron.wire.as2.factories`. The `vocab/activities/` classes are private
implementation details.
