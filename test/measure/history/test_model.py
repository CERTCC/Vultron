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

"""The event record refuses a missing or misplaced field (CEH-03-001 to CEH-03-010)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from vultron.core.models.events.base import MessageSemantics
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.states.rm import RM
from vultron.measure.history import (
    RM_EVENT_KINDS,
    CaseEvent,
    EventKind,
    EventScope,
    GapLabel,
)

_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _fields(**overrides: Any) -> dict[str, Any]:
    """A valid participant event's fields, with *overrides* applied."""
    fields: dict[str, Any] = {
        "kind": EventKind.REPORT_RECEIVED,
        "participant": "https://example.org/actors/vendor",
        "semantic_type": MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
        "log_index": 3,
        "committed_at": _AT,
    }
    fields.update(overrides)
    return fields


@pytest.mark.spec("CEH-03-001")
@pytest.mark.parametrize(
    "missing", ["kind", "semantic_type", "log_index", "committed_at"]
)
def test_a_record_missing_a_required_field_is_refused(missing):
    fields = _fields()
    del fields[missing]
    with pytest.raises(ValidationError):
        CaseEvent(**fields)


@pytest.mark.spec("CEH-03-002")
def test_the_kind_comes_from_a_closed_enumeration():
    with pytest.raises(ValidationError):
        CaseEvent(**_fields(kind="report_reopened"))
    assert CaseEvent(**_fields(kind=CSEvent.V)).kind is CSEvent.V


@pytest.mark.spec("CEH-03-002")
@pytest.mark.spec("CEH-04-002")
def test_every_report_management_state_entered_has_a_kind():
    assert set(RM_EVENT_KINDS) == set(RM) - {RM.START}
    assert len(set(RM_EVENT_KINDS.values())) == len(RM_EVENT_KINDS)


@pytest.mark.spec("CEH-03-003")
def test_a_participant_event_names_its_participant():
    with pytest.raises(ValidationError, match="name its participant"):
        CaseEvent(**_fields(participant=None))
    event = CaseEvent(**_fields())
    assert event.scope is EventScope.PARTICIPANT
    assert event.participant == "https://example.org/actors/vendor"


@pytest.mark.spec("CEH-03-004")
def test_a_case_event_records_the_case_rather_than_a_participant():
    with pytest.raises(ValidationError, match="must not name a participant"):
        CaseEvent(**_fields(kind=CSEvent.P))
    event = CaseEvent(**_fields(kind=CSEvent.P, participant=None))
    assert event.scope is EventScope.CASE
    assert event.model_dump()["scope"] == "case"


@pytest.mark.spec("CEH-03-005")
@pytest.mark.spec("CEH-03-006")
@pytest.mark.spec("CEH-03-009")
def test_the_record_carries_index_stamp_and_semantic_type():
    event = CaseEvent(**_fields())
    assert event.log_index == 3
    assert event.committed_at == _AT
    assert (
        event.semantic_type
        is MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
    )
    with pytest.raises(ValidationError):
        CaseEvent(**_fields(log_index=-1))
    with pytest.raises(ValidationError):
        CaseEvent(**_fields(semantic_type="not_a_semantic_type"))


@pytest.mark.spec("CEH-03-007")
@pytest.mark.spec("CEH-03-008")
def test_the_claimed_time_is_its_own_field_and_may_be_absent():
    claimed = datetime(2025, 12, 31, tzinfo=UTC)
    assert CaseEvent(**_fields(claimed_at=claimed)).claimed_at == claimed
    assert CaseEvent(**_fields()).claimed_at is None


@pytest.mark.spec("CEH-03-010")
def test_gap_labels_come_from_a_closed_enumeration_once_each():
    event = CaseEvent(**_fields(gaps=[GapLabel.SEATED_AT_CREATION]))
    assert event.gaps == [GapLabel.SEATED_AT_CREATION]
    with pytest.raises(ValidationError):
        CaseEvent(**_fields(gaps=["stamped_by_magic"]))
    with pytest.raises(ValidationError, match="listed twice"):
        CaseEvent(
            **_fields(
                gaps=[GapLabel.SEATED_AT_CREATION, GapLabel.SEATED_AT_CREATION]
            )
        )


@pytest.mark.spec("CEH-04-009")
def test_a_consent_event_must_name_its_embargo():
    with pytest.raises(ValidationError, match="name its embargo"):
        CaseEvent(**_fields(kind=EventKind.CONSENT_AGREED))
    with pytest.raises(ValidationError, match="names no embargo"):
        CaseEvent(**_fields(embargo_id="urn:uuid:embargo-1"))


@pytest.mark.spec("CEH-04-006")
def test_an_embargo_exit_must_carry_its_reason_and_only_it_may():
    exit_fields = _fields(
        kind=EventKind.EMBARGO_EXIT,
        participant=None,
        embargo_id="urn:uuid:embargo-1",
    )
    with pytest.raises(ValidationError, match="carry its reason"):
        CaseEvent(**exit_fields)
    event = CaseEvent(
        **exit_fields, exit_reason=TerminationReason.END_TIME_REACHED
    )
    assert event.exit_reason is TerminationReason.END_TIME_REACHED
    with pytest.raises(ValidationError, match="only an embargo exit"):
        CaseEvent(**_fields(exit_reason=TerminationReason.EARLY))
    with pytest.raises(ValidationError, match="only an embargo exit"):
        CaseEvent(**_fields(exit_cause={"kind": "OTHER"}))


def test_only_an_embargo_start_replaces_an_embargo():
    with pytest.raises(ValidationError, match="only an embargo start"):
        CaseEvent(**_fields(replaces_embargo_id="urn:uuid:embargo-0"))
