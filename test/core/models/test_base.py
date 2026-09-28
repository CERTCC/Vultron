"""Tests for CoreObject base class and domain model inheritance."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from vultron.core.models.activity import (
    VultronAccept,
    VultronActivity,
    VultronCreateCaseActivity,
    VultronOffer,
)
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.note import VultronNote
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport

DOMAIN_OBJECT_CLASSES = [
    VulnerabilityReport,
    VulnerabilityCase,
    VultronNote,
    CaseParticipant,
    CaseStatus,
    EmbargoEvent,
    CaseActor,
    VultronActivity,
    VultronOffer,
    VultronAccept,
    VultronCreateCaseActivity,
]

_FUTURE_DT = datetime(2030, 1, 1, tzinfo=timezone.utc)

REQUIRED_KWARGS: dict[type, dict] = {
    VultronNote: {"content": "test content"},
    CaseParticipant: {
        "context": "urn:uuid:case-123",
    },
    CaseStatus: {
        "context": "urn:uuid:case-123",
        "attributed_to": "urn:uuid:actor-456",
    },
    EmbargoEvent: {
        "context": "urn:uuid:case-123",
        "end_time": _FUTURE_DT,
    },
    VultronActivity: {
        "type_": "Announce",
        "actor": "https://example.org/actors/test",
    },
    VultronOffer: {"actor": "https://example.org/actors/test"},
    VultronAccept: {"actor": "https://example.org/actors/test"},
    VultronCreateCaseActivity: {"actor": "https://example.org/actors/test"},
}


def make_instance(cls, **extra):
    """Create a domain object instance with minimum required fields plus any extras."""
    kwargs = dict(REQUIRED_KWARGS.get(cls, {}))
    kwargs.update(extra)
    return cls(**kwargs)


@pytest.mark.parametrize("cls", DOMAIN_OBJECT_CLASSES)
def test_inherits_from_core_object(cls):
    assert issubclass(cls, CoreObject)


@pytest.mark.parametrize("cls", DOMAIN_OBJECT_CLASSES)
def test_has_as_id(cls):
    obj = make_instance(cls)
    assert obj.id_.startswith("urn:uuid:")


@pytest.mark.parametrize("cls", DOMAIN_OBJECT_CLASSES)
def test_has_as_type(cls):
    obj = make_instance(cls)
    assert obj.type_


#: Classes that derive a display ``name`` from their own state when the caller
#: supplies none, so ``name`` is legitimately non-None on a bare instance.
#: ADR-0099 detail 5 moved that derivation from the wire class onto the core
#: class, which is what makes these the exception — the label is a function of
#: the object's state, and the class that holds the state owns it.
DERIVES_ITS_OWN_NAME = frozenset({CaseStatus, EmbargoEvent})


@pytest.mark.parametrize("cls", DOMAIN_OBJECT_CLASSES)
def test_has_name_field(cls):
    obj = make_instance(cls)
    if cls in DERIVES_ITS_OWN_NAME:
        assert obj.name, f"{cls.__name__} should derive a display name"
    else:
        assert obj.name is None
    named = make_instance(cls, name="test")
    assert named.name == "test", "an explicit name must always win"


def test_vultron_participant_status_context_required():
    with pytest.raises(ValidationError):
        ParticipantStatus()
    ps = ParticipantStatus(context="urn:uuid:case-123")
    assert issubclass(ParticipantStatus, CoreObject)
    assert ps.id_.startswith("urn:uuid:")
    assert ps.type_ == "ParticipantStatus"
    assert ps.context == "urn:uuid:case-123"


def test_vultron_activity_as_type_required():
    with pytest.raises(ValidationError):
        VultronActivity(  # pyright: ignore[reportCallIssue]
            actor="https://example.org/actors/test"
        )
    act = VultronActivity(
        type_="Offer", actor="https://example.org/actors/test"
    )
    assert act.type_ == "Offer"


def test_domain_object_as_id_unique():
    a = VulnerabilityReport()
    b = VulnerabilityReport()
    assert a.id_ != b.id_


def test_domain_object_expected_as_types():
    assert VulnerabilityReport().type_ == "VulnerabilityReport"
    assert VulnerabilityCase().type_ == "VulnerabilityCase"
    assert VultronNote(content="test").type_ == "Note"
    assert (
        CaseParticipant(context="urn:uuid:c", attributed_to="urn:uuid:a").type_
        == "CaseParticipant"
    )
    assert (
        CaseStatus(context="urn:uuid:c", attributed_to="urn:uuid:a").type_
        == "CaseStatus"
    )
    assert (
        EmbargoEvent(context="urn:uuid:c", end_time=_FUTURE_DT).type_
        == "EmbargoEvent"
    )
    assert CaseActor().type_ == "Service"
    _test_actor = "https://example.org/actors/test"
    assert VultronOffer(actor=_test_actor).type_ == "Offer"
    assert VultronAccept(actor=_test_actor).type_ == "Accept"
    assert VultronCreateCaseActivity(actor=_test_actor).type_ == "Create"


def test_vultron_note_content_required():
    with pytest.raises(Exception):
        VultronNote()
    note = VultronNote(content="test content")
    assert note.content == "test content"


def test_vultron_participant_required_fields():
    """CaseParticipant has no required fields (migrated to CoreObject).

    Both context and attributed_to are optional; when attributed_to is
    provided, name is auto-derived from it.
    """
    p_empty = CaseParticipant()
    assert p_empty.context is None

    p = CaseParticipant(
        context="urn:uuid:case-123", attributed_to="urn:uuid:actor-456"
    )
    assert p.context == "urn:uuid:case-123"
    assert p.attributed_to == "urn:uuid:actor-456"
    assert p.name == "urn:uuid:actor-456"


def test_vultron_case_status_required_fields():
    with pytest.raises(Exception):
        CaseStatus()
    # attributed_to is optional; context alone is sufficient
    cs_no_attr = CaseStatus(context="urn:uuid:case-123")
    assert cs_no_attr.context == "urn:uuid:case-123"
    assert cs_no_attr.attributed_to is None
    cs = CaseStatus(
        context="urn:uuid:case-123", attributed_to="urn:uuid:actor-456"
    )
    assert cs.context == "urn:uuid:case-123"
    assert cs.attributed_to == "urn:uuid:actor-456"


def test_vultron_embargo_event_required_fields():
    # context is required; omitting it must raise
    with pytest.raises(Exception):
        EmbargoEvent()
    # end_time is optional (has a default); context alone is sufficient
    em_default = EmbargoEvent(context="urn:uuid:case-123")
    assert em_default.context == "urn:uuid:case-123"
    assert em_default.end_time is not None
    # explicit end_time is also accepted
    em = EmbargoEvent(context="urn:uuid:case-123", end_time=_FUTURE_DT)
    assert em.context == "urn:uuid:case-123"
    assert em.end_time == _FUTURE_DT


def test_vultron_case_init_case_statuses():
    case_no_actor = VulnerabilityCase()
    assert case_no_actor.case_statuses == []

    case_with_actor = VulnerabilityCase(attributed_to="urn:uuid:actor-123")
    assert len(case_with_actor.case_statuses) == 1
    assert isinstance(case_with_actor.case_statuses[0], CaseStatus)
    assert case_with_actor.case_statuses[0].context == case_with_actor.id_
    assert (
        case_with_actor.case_statuses[0].attributed_to == "urn:uuid:actor-123"
    )

    case_existing_statuses = VulnerabilityCase(
        attributed_to="urn:uuid:actor-123",
        case_statuses=[
            CaseStatus(
                context="urn:uuid:case-123", attributed_to="urn:uuid:actor-456"
            )
        ],
    )
    assert len(case_existing_statuses.case_statuses) == 1
    assert isinstance(case_existing_statuses.case_statuses[0], CaseStatus)
    assert case_existing_statuses.case_statuses[0].attributed_to is not None
    assert (
        case_existing_statuses.case_statuses[0].attributed_to
        == "urn:uuid:actor-456"
    )


def test_vultron_case_rewrites_status_context_to_case_id():
    """An inline status belongs to the case holding it (``set_cs_context``)."""
    case = VulnerabilityCase(
        case_statuses=[
            CaseStatus(context="urn:uuid:other", attributed_to="urn:uuid:a")
        ],
    )
    status = case.case_statuses[0]
    assert isinstance(status, CaseStatus)
    assert status.context == case.id_
