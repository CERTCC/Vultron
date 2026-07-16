"""Tests that each event class's named property aliases resolve to the correct
underlying base field on VultronEvent.

Each parametrized case populates the relevant source field(s) on an event
instance and asserts that every named alias returns the same value as its
backing base property.  Multi-alias classes are checked as a unit so a
copy/paste mistake in any property on the same class cannot pass undetected.
"""

import pytest

from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import VultronObject
from vultron.core.models.case import VultronCase
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_event import VultronEmbargoEvent
from vultron.core.models.events.actor import (
    AcceptCaseManagerRoleReceivedEvent,
    AcceptCaseOwnershipTransferReceivedEvent,
    AcceptInviteActorToCaseReceivedEvent,
    RejectCaseManagerRoleReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.case import (
    AddReportToCaseReceivedEvent,
    CloseCaseReceivedEvent,
    CreateCaseReceivedEvent,
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
    UpdateCaseReceivedEvent,
)
from vultron.core.models.events.case_participant import (
    AddCaseParticipantToCaseReceivedEvent,
    CreateCaseParticipantReceivedEvent,
    RemoveCaseParticipantFromCaseReceivedEvent,
)
from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
    AddEmbargoEventToCaseReceivedEvent,
    AnnounceEmbargoEventToCaseReceivedEvent,
    CreateEmbargoEventReceivedEvent,
    RejectInviteToEmbargoOnCaseReceivedEvent,
    RemoveEmbargoEventFromCaseReceivedEvent,
)
from vultron.core.models.events.note import (
    AddNoteToCaseReceivedEvent,
    CreateNoteReceivedEvent,
    RemoveNoteFromCaseReceivedEvent,
)
from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    CloseReportReceivedEvent,
    CreateReportReceivedEvent,
    InvalidateReportReceivedEvent,
    SubmitReportReceivedEvent,
    ValidateReportReceivedEvent,
)
from vultron.core.models.events.status import (
    AddCaseStatusToCaseReceivedEvent,
    AddParticipantStatusToParticipantReceivedEvent,
    CreateCaseStatusReceivedEvent,
    CreateParticipantStatusReceivedEvent,
)
from vultron.core.models.note import VultronNote
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VultronReport

# Shared required fields for all VultronEvent instances.
_ACT_ID = "https://example.org/activities/act-1"
_ACTOR_ID = "https://example.org/actors/alice"

# Fixed domain objects reused across test cases so identity checks are reliable.
_CASE_URI = "https://example.org/cases/c1"
_ACTOR_URI = "https://example.org/actors/alice"

_report = VultronReport(id_="https://example.org/reports/r1")
_case = VultronCase(id_=_CASE_URI)
_note = VultronNote(
    id_="https://example.org/notes/n1",
    content="test note",
)
_participant = VultronParticipant(
    id_="https://example.org/participants/p1",
    context=_CASE_URI,
    attributed_to=_ACTOR_URI,
)
_case_status = CaseStatus(
    id_="https://example.org/statuses/cs1",
    context=_CASE_URI,
    attributed_to=_ACTOR_URI,
)
_participant_status = ParticipantStatus(
    id_="https://example.org/statuses/ps1",
    context=_CASE_URI,
)
_embargo = VultronEmbargoEvent(
    id_="https://example.org/embargoes/e1",
    context=_CASE_URI,
)
_activity = VultronActivity(
    id_="https://example.org/activities/offer-1",
    type_="Offer",
    actor=_ACTOR_URI,
)
_obj = VultronObject(id_="https://example.org/objects/o1")


def _mk(cls, semantic, **fields):
    """Construct an event with the required base fields and extra field overrides."""
    return cls(
        semantic_type=semantic,
        activity_id=_ACT_ID,
        actor_id=_ACTOR_ID,
        **fields,
    )


# Each row: (event_class, semantic, field_kwargs, list of (alias, base_attr) pairs)
# All named aliases on multi-alias classes are verified in a single event
# instance to catch any cross-wiring bugs.
_CASES = [
    # ── report.py ────────────────────────────────────────────────────────────
    (
        CreateReportReceivedEvent,
        MessageSemantics.CREATE_REPORT,
        {"object_": _report},
        [("report_id", "object_id"), ("report", "object_")],
    ),
    (
        SubmitReportReceivedEvent,
        MessageSemantics.SUBMIT_REPORT,
        {"object_": _report},
        [("report_id", "object_id"), ("report", "object_")],
    ),
    (
        ValidateReportReceivedEvent,
        MessageSemantics.VALIDATE_REPORT,
        {"object_": _activity, "inner_object": _report},
        [
            ("offer_id", "object_id"),
            ("offer", "object_"),
            ("report_id", "inner_object_id"),
            ("report", "inner_object"),
        ],
    ),
    (
        InvalidateReportReceivedEvent,
        MessageSemantics.INVALIDATE_REPORT,
        {"object_": _activity, "inner_object": _report},
        [
            ("offer_id", "object_id"),
            ("offer", "object_"),
            ("report_id", "inner_object_id"),
            ("report", "inner_object"),
        ],
    ),
    (
        AckReportReceivedEvent,
        MessageSemantics.ACK_REPORT,
        {"object_": _activity, "inner_object": _report},
        [
            ("offer_id", "object_id"),
            ("offer", "object_"),
            ("report_id", "inner_object_id"),
            ("report", "inner_object"),
        ],
    ),
    (
        CloseReportReceivedEvent,
        MessageSemantics.CLOSE_REPORT,
        {"object_": _activity, "inner_object": _report},
        [
            ("offer_id", "object_id"),
            ("offer", "object_"),
            ("report_id", "inner_object_id"),
            ("report", "inner_object"),
        ],
    ),
    # ── case.py ───────────────────────────────────────────────────────────────
    (
        CreateCaseReceivedEvent,
        MessageSemantics.CREATE_CASE,
        {"object_": _case, "activity": _activity},
        [("case_id", "object_id"), ("case", "object_")],
    ),
    (
        UpdateCaseReceivedEvent,
        MessageSemantics.UPDATE_CASE,
        {"object_": _case},
        [("case_id", "object_id"), ("case", "object_")],
    ),
    (
        EngageCaseReceivedEvent,
        MessageSemantics.ENGAGE_CASE,
        {"object_": _case},
        [("case_id", "object_id"), ("case", "object_")],
    ),
    (
        DeferCaseReceivedEvent,
        MessageSemantics.DEFER_CASE,
        {"object_": _case},
        [("case_id", "object_id"), ("case", "object_")],
    ),
    (
        AddReportToCaseReceivedEvent,
        MessageSemantics.ADD_REPORT_TO_CASE,
        {"object_": _report, "target": _case},
        [
            ("report_id", "object_id"),
            ("report", "object_"),
            ("case_id", "target_id"),
            ("case", "target"),
        ],
    ),
    (
        CloseCaseReceivedEvent,
        MessageSemantics.CLOSE_CASE,
        {"object_": _case},
        [("case_id", "object_id"), ("case", "object_")],
    ),
    # ── actor.py ──────────────────────────────────────────────────────────────
    (
        AcceptCaseManagerRoleReceivedEvent,
        MessageSemantics.ACCEPT_CASE_MANAGER_ROLE,
        {"inner_object": _case},
        [("case_id", "inner_object_id"), ("case", "inner_object")],
    ),
    (
        RejectCaseManagerRoleReceivedEvent,
        MessageSemantics.REJECT_CASE_MANAGER_ROLE,
        {"object_": _activity},
        [("offer_id", "object_id"), ("offer", "object_")],
    ),
    (
        AcceptCaseOwnershipTransferReceivedEvent,
        MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER,
        {"inner_object": _case},
        [("case_id", "inner_object_id"), ("case", "inner_object")],
    ),
    (
        RejectCaseOwnershipTransferReceivedEvent,
        MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER,
        {"object_": _activity},
        [("offer_id", "object_id"), ("offer", "object_")],
    ),
    (
        AcceptInviteActorToCaseReceivedEvent,
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
        {"inner_target": _case, "inner_object": _obj},
        [
            ("case_id", "inner_target_id"),
            ("case", "inner_target"),
            ("invitee_id", "inner_object_id"),
            ("invitee", "inner_object"),
        ],
    ),
    (
        RejectInviteActorToCaseReceivedEvent,
        MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE,
        {"object_": _activity},
        [("invite_id", "object_id"), ("invite", "object_")],
    ),
    # ── case_participant.py ───────────────────────────────────────────────────
    (
        CreateCaseParticipantReceivedEvent,
        MessageSemantics.CREATE_CASE_PARTICIPANT,
        {"object_": _participant},
        [("participant_id", "object_id"), ("participant", "object_")],
    ),
    (
        AddCaseParticipantToCaseReceivedEvent,
        MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE,
        {"object_": _participant, "target": _case},
        [
            ("participant_id", "object_id"),
            ("participant", "object_"),
            ("case_id", "target_id"),
            ("case", "target"),
        ],
    ),
    (
        RemoveCaseParticipantFromCaseReceivedEvent,
        MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE,
        {"object_": _participant, "target": _case},
        [
            ("participant_id", "object_id"),
            ("participant", "object_"),
            ("case_id", "target_id"),
            ("case", "target"),
        ],
    ),
    # ── embargo.py ────────────────────────────────────────────────────────────
    (
        CreateEmbargoEventReceivedEvent,
        MessageSemantics.CREATE_EMBARGO_EVENT,
        {"object_": _embargo},
        [("embargo_id", "object_id"), ("embargo", "object_")],
    ),
    (
        AddEmbargoEventToCaseReceivedEvent,
        MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE,
        {"object_": _embargo, "target": _case},
        [
            ("embargo_id", "object_id"),
            ("embargo", "object_"),
            ("case_id", "target_id"),
            ("case", "target"),
        ],
    ),
    (
        RemoveEmbargoEventFromCaseReceivedEvent,
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
        {"object_": _embargo, "origin": _case},
        [
            ("embargo_id", "object_id"),
            ("embargo", "object_"),
            ("case_id", "origin_id"),
            ("case", "origin"),
        ],
    ),
    (
        AnnounceEmbargoEventToCaseReceivedEvent,
        MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE,
        {"context": _case},
        [("case_id", "context_id"), ("case", "context")],
    ),
    (
        AcceptInviteToEmbargoOnCaseReceivedEvent,
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        {
            "object_": _activity,
            "inner_object": _embargo,
            "inner_context": _case,
        },
        [
            ("invite_id", "object_id"),
            ("invite", "object_"),
            ("embargo_id", "inner_object_id"),
            ("embargo", "inner_object"),
            ("case_id", "inner_context_id"),
            ("case", "inner_context"),
        ],
    ),
    (
        RejectInviteToEmbargoOnCaseReceivedEvent,
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        {"object_": _activity},
        [("invite_id", "object_id"), ("invite", "object_")],
    ),
    # ── note.py ───────────────────────────────────────────────────────────────
    (
        CreateNoteReceivedEvent,
        MessageSemantics.CREATE_NOTE,
        {"object_": _note},
        [("note_id", "object_id"), ("note", "object_")],
    ),
    (
        AddNoteToCaseReceivedEvent,
        MessageSemantics.ADD_NOTE_TO_CASE,
        {"object_": _note, "target": _case},
        [
            ("note_id", "object_id"),
            ("note", "object_"),
            ("case_id", "target_id"),
            ("case", "target"),
        ],
    ),
    (
        RemoveNoteFromCaseReceivedEvent,
        MessageSemantics.REMOVE_NOTE_FROM_CASE,
        {"object_": _note, "target": _case},
        [
            ("note_id", "object_id"),
            ("note", "object_"),
            ("case_id", "target_id"),
            ("case", "target"),
        ],
    ),
    # ── status.py ─────────────────────────────────────────────────────────────
    (
        CreateCaseStatusReceivedEvent,
        MessageSemantics.CREATE_CASE_STATUS,
        {"object_": _case_status},
        [("status_id", "object_id"), ("status", "object_")],
    ),
    (
        AddCaseStatusToCaseReceivedEvent,
        MessageSemantics.ADD_CASE_STATUS_TO_CASE,
        {"object_": _case_status, "target": _case},
        [
            ("status_id", "object_id"),
            ("status", "object_"),
            ("case_id", "target_id"),
            ("case", "target"),
        ],
    ),
    (
        CreateParticipantStatusReceivedEvent,
        MessageSemantics.CREATE_PARTICIPANT_STATUS,
        {"object_": _participant_status},
        [("status_id", "object_id"), ("status", "object_")],
    ),
    (
        AddParticipantStatusToParticipantReceivedEvent,
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
        {"object_": _participant_status, "target": _participant},
        [
            ("status_id", "object_id"),
            ("status", "object_"),
            ("participant_id", "target_id"),
            ("participant", "target"),
        ],
    ),
]


@pytest.mark.parametrize(
    "cls,semantic,fields,alias_pairs",
    _CASES,
    ids=[c[0].__name__ for c in _CASES],
)
def test_named_aliases_resolve_to_correct_base_fields(
    cls, semantic, fields, alias_pairs
):
    """Each named alias must return the same value as its backing base field."""
    event = _mk(cls, semantic, **fields)
    for alias, base in alias_pairs:
        alias_val = getattr(event, alias)
        base_val = getattr(event, base)
        assert alias_val == base_val, (
            f"{cls.__name__}.{alias} should equal .{base}, "
            f"but got {alias_val!r} vs {base_val!r}"
        )


@pytest.mark.parametrize(
    "cls,semantic,alias_names",
    [
        (
            CreateReportReceivedEvent,
            MessageSemantics.CREATE_REPORT,
            ["report_id", "report"],
        ),
        (
            SubmitReportReceivedEvent,
            MessageSemantics.SUBMIT_REPORT,
            ["report_id", "report"],
        ),
        (
            UpdateCaseReceivedEvent,
            MessageSemantics.UPDATE_CASE,
            ["case_id", "case"],
        ),
        (
            CreateNoteReceivedEvent,
            MessageSemantics.CREATE_NOTE,
            ["note_id", "note"],
        ),
        (
            CreateEmbargoEventReceivedEvent,
            MessageSemantics.CREATE_EMBARGO_EVENT,
            ["embargo_id", "embargo"],
        ),
        (
            CreateCaseParticipantReceivedEvent,
            MessageSemantics.CREATE_CASE_PARTICIPANT,
            ["participant_id", "participant"],
        ),
    ],
    ids=lambda x: x.__name__ if hasattr(x, "__name__") else str(x),
)
def test_aliases_return_none_when_backing_field_is_absent(
    cls, semantic, alias_names
):
    """Named aliases must return None when the backing VultronEvent field is not set."""
    event = _mk(cls, semantic)
    for alias in alias_names:
        assert (
            getattr(event, alias) is None
        ), f"{cls.__name__}.{alias} should be None when backing field is absent"
