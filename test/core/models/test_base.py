"""Tests for VultronObject base class and domain model inheritance."""

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


@pytest.mark.parametrize("cls", DOMAIN_OBJECT_CLASSES)
def test_inherits_from_vultron_object(cls):
    assert issubclass(cls, VultronObject)


@pytest.mark.parametrize("cls", DOMAIN_OBJECT_CLASSES)
def test_has_as_id(cls):
    if cls is VultronActivity:
        obj = cls(as_type="Announce")
    else:
        obj = cls()
    assert obj.as_id.startswith("urn:uuid:")


@pytest.mark.parametrize("cls", DOMAIN_OBJECT_CLASSES)
def test_has_as_type(cls):
    if cls is VultronActivity:
        obj = cls(as_type="Announce")
        assert obj.as_type == "Announce"
    else:
        obj = cls()
        assert obj.as_type


@pytest.mark.parametrize("cls", DOMAIN_OBJECT_CLASSES)
def test_has_name_field(cls):
    if cls is VultronActivity:
        obj = cls(as_type="Announce")
    else:
        obj = cls()
    assert obj.name is None

    if cls is VultronActivity:
        named = cls(as_type="Announce", name="test")
    else:
        named = cls(name="test")
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
    assert VultronNote().as_type == "Note"
    assert VultronParticipant().as_type == "CaseParticipant"
    assert VultronCaseStatus().as_type == "CaseStatus"
    assert VultronEmbargoEvent().as_type == "Event"
    assert VultronCaseActor().as_type == "Service"
    assert VultronOffer().as_type == "Offer"
    assert VultronAccept().as_type == "Accept"
    assert VultronCreateCaseActivity().as_type == "Create"
