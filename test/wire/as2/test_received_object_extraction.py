#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""A received object reaches core as received, end to end (#5265).

Each row of #5265's table, parsed, rehydrated and extracted: a typed
reference is routed with the object the receiver holds, or, when it does not
hold it, goes on as a bare id to fetch (MV-10-011, AKM-05-007).  No step
invents state for a received object: the event carries the participant's own
statuses, never a fresh ``START`` one (AKM-02-006, ARCH-25-009).
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from test.support.case_manager import (
    CASE_MANAGER_ID,
    make_case_with_case_manager,
)
from test.support.objects import make
from test.support.received import TEST_SENDER_POSITION
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.base import CoreObject
from vultron.core.models.case_participant.participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events import MessageSemantics
from vultron.core.models.note import VultronNote
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.semantic_registry import extract_event, find_matching_semantics
from vultron.wire.as2.extractor._builders.objects import (
    _build_participant_object,
    _participant_ref_to_domain,
)
from vultron.wire.as2.extractor._pattern import bare_object_id
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.rehydration import rehydrate
from vultron.wire.as2.typed_reference import as_TypedReference
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)

_PUBLISHED = "2026-10-26T12:00:00Z"
_RECEIVER = "https://example.org/actors/vendor"


def _activity(
    activity_type: str, obj: object, case_id: str, **extra: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": activity_type,
        "id": f"https://example.org/activities/{activity_type.lower()}-1",
        "published": _PUBLISHED,
        "actor": CASE_MANAGER_ID,
        "object": obj,
        "context": case_id,
        "ledgerPosition": TEST_SENDER_POSITION.model_dump(by_alias=True),
    }
    body.update(extra)
    return body


def _received(
    body: dict[str, Any], dl: SqliteDataLayer
) -> as_TransitiveActivity:
    """*body* as the inbox routes it: parsed, then rehydrated from *dl*."""
    rehydrated = rehydrate(parse_activity(body), dl=dl)
    assert isinstance(rehydrated, as_TransitiveActivity)
    return rehydrated


@pytest.fixture
def store() -> tuple[SqliteDataLayer, str, CaseParticipant]:
    """A receiver's store holding a case and its one participant."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    case = make_case_with_case_manager(dl)
    (participant_id,) = case.case_participants
    assert isinstance(participant_id, str)
    participant = dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    return dl, case.id_, participant


def _held_object(dl: SqliteDataLayer, case_id: str, type_: str) -> CoreObject:
    """Store and return a held object of the table row *type_*."""
    if type_ == "CaseParticipant":
        participant = make(
            CaseParticipant,
            attributed_to="https://example.org/actors/finder",
            context=case_id,
        )
        dl.create(participant)
        return participant
    if type_ == "Note":
        held: CoreObject = make(
            VultronNote, content="the vendor confirmed", context=case_id
        )
    elif type_ == "Event":
        held = make(
            EmbargoEvent,
            context=case_id,
            end_time=datetime(2026, 12, 1, tzinfo=UTC),
        )
    else:
        held = make(
            VulnerabilityReport,
            content="a buffer overflow",
            attributed_to="https://example.org/actors/finder",
        )
    dl.create(held)
    return held


#: Each row of #5265's table: the type, the activity that names an object of
#: it, and the semantics the whole object routes to.
_ROWS: list[tuple[str, str, MessageSemantics]] = [
    (
        "CaseParticipant",
        "Remove",
        MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE,
    ),
    ("Note", "Add", MessageSemantics.ADD_NOTE_TO_CASE),
    ("Event", "Invite", MessageSemantics.INVITE_TO_EMBARGO_ON_CASE),
    ("VulnerabilityReport", "Offer", MessageSemantics.SUBMIT_REPORT),
]


def _row_body(
    activity_type: str, reference: dict[str, Any], case_id: str
) -> dict[str, Any]:
    if activity_type == "Offer":
        return _activity(activity_type, reference, case_id)
    return _activity(activity_type, reference, case_id, target=case_id)


@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("AKM-02-006")
@pytest.mark.parametrize(
    ("type_", "activity_type", "semantics"),
    _ROWS,
    ids=[row[0] for row in _ROWS],
)
def test_a_reference_to_a_held_object_reaches_core_as_held(
    store: tuple[SqliteDataLayer, str, CaseParticipant],
    type_: str,
    activity_type: str,
    semantics: MessageSemantics,
) -> None:
    """Parsed, rehydrated and extracted, a typed reference to a held object
    routes by its type and the event carries the held object's content."""
    dl, case_id, _ = store
    held = _held_object(dl, case_id, type_)
    reference = {"id": held.id_, "type": type_}

    body = _row_body(activity_type, reference, case_id)
    parsed = parse_activity(body)
    assert isinstance(getattr(parsed, "object_", None), as_TypedReference)
    event = extract_event(_received(body, dl))

    assert event.semantic_type is semantics
    received = event.object_
    assert isinstance(received, type(held))
    assert received.id_ == held.id_
    assert getattr(received, "content", None) == getattr(held, "content", None)
    if isinstance(held, CaseParticipant):
        assert isinstance(received, CaseParticipant)
        assert received.participant_statuses == held.participant_statuses


@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("AKM-05-007")
@pytest.mark.parametrize(
    ("type_", "activity_type"),
    [row[:2] for row in _ROWS],
    ids=[row[0] for row in _ROWS],
)
def test_a_reference_to_an_object_not_held_is_fetched_not_filled_in(
    store: tuple[SqliteDataLayer, str, CaseParticipant],
    type_: str,
    activity_type: str,
) -> None:
    """A reference the receiver cannot resolve reaches no handler as an
    object: it is routed as unresolvable and names the object to fetch."""
    dl, case_id, _ = store
    missing = f"https://example.org/objects/not-held-{type_}"

    rehydrated = _received(
        _row_body(activity_type, {"id": missing, "type": type_}, case_id), dl
    )

    assert (
        find_matching_semantics(rehydrated)
        is MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
    )
    assert bare_object_id(rehydrated) == missing
    event = extract_event(rehydrated)
    assert getattr(event, "unresolved_object_id", None) == missing
    # Core gets the id alone, with no class and so no class defaults.
    assert event.object_ is not None
    assert event.object_.type_ is None
    assert not isinstance(
        event.object_,
        (CaseParticipant, VultronNote, EmbargoEvent, VulnerabilityReport),
    )


@pytest.mark.spec("AKM-02-006")
@pytest.mark.spec("ARCH-25-009")
@pytest.mark.parametrize(
    "named_by", ["typed reference", "bare id"], ids=["reference", "bare-id"]
)
def test_a_held_participant_reaches_the_remove_event_as_held(
    store: tuple[SqliteDataLayer, str, CaseParticipant], named_by: str
) -> None:
    """``Remove`` of a held participant carries the participant's own
    record: its statuses, membership and removal fact, with no fresh
    ``START`` status minted for it (#5265)."""
    dl, case_id, participant = store
    name: object = (
        {"id": participant.id_, "type": "CaseParticipant"}
        if named_by == "typed reference"
        else participant.id_
    )

    event = extract_event(
        _received(_activity("Remove", name, case_id, target=case_id), dl)
    )

    assert (
        event.semantic_type
        is MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE
    )
    received = event.object_
    assert isinstance(received, CaseParticipant)
    assert received.model_dump() == participant.model_dump()


@pytest.mark.spec("AKM-02-006")
def test_a_whole_participant_reaches_core_with_the_statuses_it_carries(
    store: tuple[SqliteDataLayer, str, CaseParticipant],
) -> None:
    """A participant sent whole keeps every status and fact it carries."""
    _, case_id, _ = store
    sent = make(
        CaseParticipant,
        attributed_to="https://example.org/actors/finder",
        context=case_id,
        joined=False,
        removal_activity="https://example.org/activities/remove-0",
        embargo_consents=[
            EmbargoConsent(
                embargo_id="https://example.org/embargoes/1",
                state=EmbargoConsentState.DECLINED,
            )
        ],
        participant_statuses=[
            make(
                ParticipantStatus,
                context=case_id,
                rm=RM.ACCEPTED,
                case_engagement=False,
            )
        ],
    )

    event = extract_event(
        parse_activity(
            _activity(
                "Add",
                sent.model_dump(by_alias=True, mode="json", exclude_none=True),
                case_id,
                target=case_id,
            )
        )
    )

    received = event.object_
    assert isinstance(received, CaseParticipant)
    assert received.participant_statuses == sent.participant_statuses
    assert received.joined is False
    assert received.removal_activity == sent.removal_activity
    assert received.embargo_consents == sent.embargo_consents


@pytest.mark.spec("AKM-02-006")
def test_a_received_participant_status_keeps_its_engagement(
    store: tuple[SqliteDataLayer, str, CaseParticipant],
) -> None:
    """A status saying the participant is not engaged is not read back as
    engaged by the status model's default (#5265)."""
    _, case_id, participant = store
    status = make(
        ParticipantStatus,
        context=case_id,
        attributed_to=participant.attributed_to,
        rm=RM.DEFERRED,
        case_engagement=False,
        tracking_id="VND-42",
    )

    event = extract_event(
        parse_activity(
            _activity(
                "Add",
                status.model_dump(
                    by_alias=True, mode="json", exclude_none=True
                ),
                case_id,
                target=participant.id_,
            )
        )
    )

    received = event.object_
    assert isinstance(received, ParticipantStatus)
    assert received == status


class _ParticipantLike:
    """A participant-shaped object that is not the core class."""

    id_ = "https://example.org/participants/not-core"
    attributed_to = "https://example.org/actors/finder"
    context = "https://example.org/cases/1"
    case_roles: list[str] = []
    participant_statuses: list[ParticipantStatus] = []


@pytest.mark.spec("AKM-02-006")
def test_a_participant_that_is_not_the_core_class_is_not_rebuilt() -> None:
    """Nothing hand-builds a participant from a few fields, so no ``START``
    status or ``joined`` flag is minted for one (#5265)."""
    ref = _ParticipantLike()

    assert _build_participant_object(ref) == {}
    assert _participant_ref_to_domain(ref) == ref.id_
