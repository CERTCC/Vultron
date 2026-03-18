"""Tests for VultronObject base class and domain model inheritance."""

from datetime import datetime, timezone

import pytest

from vultron.core.models.activity import (
    VultronAccept,
    VultronActivity,
    VultronCreateCaseActivity,
    VultronOffer,
)
from vultron.core.models.base import VultronObject
from vultron.core.models.case import VultronCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_status import VultronCaseStatus
from vultron.core.models.embargo_event import VultronEmbargoEvent
from vultron.core.models.note import VultronNote
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.models.report import VultronReport

DOMAIN_OBJECT_CLASSES = [
    VultronReport,
    VultronCase,
    VultronNote,
    VultronParticipant,
    VultronCaseStatus,
    VultronEmbargoEvent,
    VultronCaseActor,
    VultronActivity,
    VultronOffer,
    VultronAccept,
    VultronCreateCaseActivity,
]

_FUTURE_DT = datetime(2030, 1, 1, tzinfo=timezone.utc)

REQUIRED_KWARGS: dict[type, dict] = {
    VultronNote: {"content": "test content"},
    VultronParticipant: {
        "context": "urn:uuid:case-123",
        "attributed_to": "urn:uuid:actor-456",
    },
    VultronCaseStatus: {
        "context": "urn:uuid:case-123",
        "attributed_to": "urn:uuid:actor-456",
    },
    VultronEmbargoEvent: {
        "context": "urn:uuid:case-123",
        "end_time": _FUTURE_DT,
    },
    VultronActivity: {"as_type": "Announce"},
}


def make_instance(cls, **extra):
    """Create a domain object instance with minimum required fields plus any extras."""
    kwargs = dict(REQUIRED_KWARGS.get(cls, {}))
    kwargs.update(extra)
    return cls(**kwargs)


@pytest.mark.parametrize("cls", DOMAIN_OBJECT_CLASSES)
def test_inherits_from_vultron_object(cls):
    assert issubclass(cls, VultronObject)


@pytest.mark.parametrize("cls", DOMAIN_OBJECT_CLASSES)
def test_has_as_id(cls):
    obj = make_instance(cls)
    assert obj.as_id.startswith("urn:uuid:")


@pytest.mark.parametrize("cls", DOMAIN_OBJECT_CLASSES)
def test_has_as_type(cls):
    obj = make_instance(cls)
    assert obj.as_type


@pytest.mark.parametrize("cls", DOMAIN_OBJECT_CLASSES)
def test_has_name_field(cls):
    obj = make_instance(cls)
    assert obj.name is None
    named = make_instance(cls, name="test")
    assert named.name == "test"


def test_vultron_participant_status_context_required():
    with pytest.raises(Exception):
        VultronParticipantStatus()
    ps = VultronParticipantStatus(context="urn:uuid:case-123")
    assert issubclass(VultronParticipantStatus, VultronObject)
    assert ps.as_id.startswith("urn:uuid:")
    assert ps.as_type == "ParticipantStatus"
    assert ps.context == "urn:uuid:case-123"


def test_vultron_activity_as_type_required():
    with pytest.raises(Exception):
        VultronActivity()
    act = VultronActivity(as_type="Offer")
    assert act.as_type == "Offer"


def test_domain_object_as_id_unique():
    a = VultronReport()
    b = VultronReport()
    assert a.as_id != b.as_id


def test_domain_object_expected_as_types():
    assert VultronReport().as_type == "VulnerabilityReport"
    assert VultronCase().as_type == "VulnerabilityCase"
    assert VultronNote(content="test").as_type == "Note"
    assert (
        VultronParticipant(
            context="urn:uuid:c", attributed_to="urn:uuid:a"
        ).as_type
        == "CaseParticipant"
    )
    assert (
        VultronCaseStatus(
            context="urn:uuid:c", attributed_to="urn:uuid:a"
        ).as_type
        == "CaseStatus"
    )
    assert (
        VultronEmbargoEvent(context="urn:uuid:c", end_time=_FUTURE_DT).as_type
        == "Event"
    )
    assert VultronCaseActor().as_type == "Service"
    assert VultronOffer().as_type == "Offer"
    assert VultronAccept().as_type == "Accept"
    assert VultronCreateCaseActivity().as_type == "Create"


def test_vultron_note_content_required():
    with pytest.raises(Exception):
        VultronNote()
    note = VultronNote(content="test content")
    assert note.content == "test content"


def test_vultron_participant_required_fields():
    with pytest.raises(Exception):
        VultronParticipant()
    with pytest.raises(Exception):
        VultronParticipant(context="urn:uuid:case-123")
    p = VultronParticipant(
        context="urn:uuid:case-123", attributed_to="urn:uuid:actor-456"
    )
    assert p.context == "urn:uuid:case-123"
    assert p.attributed_to == "urn:uuid:actor-456"


def test_vultron_case_status_required_fields():
    with pytest.raises(Exception):
        VultronCaseStatus()
    with pytest.raises(Exception):
        VultronCaseStatus(context="urn:uuid:case-123")
    cs = VultronCaseStatus(
        context="urn:uuid:case-123", attributed_to="urn:uuid:actor-456"
    )
    assert cs.context == "urn:uuid:case-123"
    assert cs.attributed_to == "urn:uuid:actor-456"


def test_vultron_embargo_event_required_fields():
    with pytest.raises(Exception):
        VultronEmbargoEvent()
    with pytest.raises(Exception):
        VultronEmbargoEvent(context="urn:uuid:case-123")
    em = VultronEmbargoEvent(context="urn:uuid:case-123", end_time=_FUTURE_DT)
    assert em.context == "urn:uuid:case-123"
    assert em.end_time == _FUTURE_DT


def test_vultron_case_init_case_statuses():
    case_no_actor = VultronCase()
    assert case_no_actor.case_statuses == []

    case_with_actor = VultronCase(attributed_to="urn:uuid:actor-123")
    assert len(case_with_actor.case_statuses) == 1
    assert isinstance(case_with_actor.case_statuses[0], VultronCaseStatus)
    assert case_with_actor.case_statuses[0].context == case_with_actor.as_id
    assert (
        case_with_actor.case_statuses[0].attributed_to == "urn:uuid:actor-123"
    )

    case_existing_statuses = VultronCase(
        attributed_to="urn:uuid:actor-123",
        case_statuses=[
            VultronCaseStatus(
                context="urn:uuid:case-123", attributed_to="urn:uuid:actor-456"
            )
        ],
    )
    assert len(case_existing_statuses.case_statuses) == 1
    assert (
        case_existing_statuses.case_statuses[0].attributed_to
        == "urn:uuid:actor-456"
    )
