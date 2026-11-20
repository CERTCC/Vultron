#!/usr/bin/env python

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
"""
Unit tests for vultron.wire.as2.factories.case_participant.

Spec coverage:
- AF-01-002: Factory functions return plain AS2 base types.
- AF-01-003: Explicit, domain-typed parameters for protocol-significant fields.
- AF-04-001: Factory functions wrap ValidationError in
  VultronActivityConstructionError.
- AF-04-002: All factory functions re-exported from factories/__init__.py.
"""

import pytest

from test.support.objects import authored_at, make
from vultron.core.models._helpers import _as_id
from vultron.wire.as2.factories import (
    VultronActivityConstructionError,
    add_participant_to_case_activity,
    add_status_to_participant_activity,
    announce_admitted_act_activity,
    reinstate_participant_activity,
    remove_participant_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Announce,
    as_Create,
    as_Remove,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus

_ACTOR_URI = "https://example.org/actors/alice"
_CASE_URI = "https://example.org/cases/case-001"
_PARTICIPANT_URI = "https://example.org/participants/part-001"


@pytest.fixture
def sample_participant() -> as_CaseParticipant:
    return make(as_CaseParticipant, attributed_to=_ACTOR_URI)


@pytest.fixture
def sample_participant_status() -> as_ParticipantStatus:
    return make(as_ParticipantStatus, context=_CASE_URI)


# ---------------------------------------------------------------------------
# add_participant_to_case_activity
# ---------------------------------------------------------------------------


def _seat(participant: as_CaseParticipant, **kwargs) -> as_Add:
    return add_participant_to_case_activity(
        participant=participant,
        target=_CASE_URI,
        actor=_ACTOR_URI,
        at=authored_at(),
        **kwargs,
    )


@pytest.mark.spec("AF-01-002", "AF-01-001")
@pytest.mark.spec("VAM-06-004", "CLP-07-021", "CLP-07-007")
def test_the_seating_entry_is_an_add_to_the_case(sample_participant):
    """The record joins the case's list: ``Add``, ``target`` and ``context`` the case."""
    result = _seat(sample_participant)

    assert isinstance(result, as_Add)
    assert not isinstance(result, as_Create)
    assert result.type_ == "Add"
    assert result.target == _CASE_URI
    assert result.context == _CASE_URI
    body = result.model_dump(by_alias=True, mode="json")
    assert body["type"] == "Add"
    assert body["target"] == _CASE_URI
    assert body["context"] == _CASE_URI


@pytest.mark.spec("CM-11-024")
def test_the_seating_entry_carries_the_record_in_full(sample_participant):
    result = _seat(sample_participant)

    assert result.object_ == sample_participant


def test_the_seating_entry_auto_generates_a_name(sample_participant):
    """The wire class names the record added and its case."""
    result = _seat(sample_participant)

    assert result.name is not None
    assert "Add as_CaseParticipant" in result.name
    assert result.name.endswith(f"to {_CASE_URI}")


def test_the_seating_entry_keeps_an_explicit_name(sample_participant):
    """Explicitly provided name is not overwritten by the model validator."""
    result = _seat(sample_participant, name="My Custom Name")

    assert result.name == "My Custom Name"


@pytest.mark.spec("AF-04-001", "CLP-07-007")
def test_the_seating_entry_refuses_a_context_naming_another_case(
    sample_participant,
):
    with pytest.raises(VultronActivityConstructionError):
        _seat(sample_participant, context="https://example.org/cases/other")


@pytest.mark.spec("AF-04-001", "VAM-06-004")
def test_the_seating_entry_refuses_no_case(sample_participant):
    with pytest.raises(VultronActivityConstructionError):
        add_participant_to_case_activity(
            participant=sample_participant,
            target=None,  # type: ignore[arg-type]
            actor=_ACTOR_URI,
            at=authored_at(),
        )


@pytest.mark.spec("AF-04-001")
def test_the_seating_entry_refuses_an_invalid_participant():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        add_participant_to_case_activity(
            participant="not-a-participant",  # type: ignore[arg-type]
            target=_CASE_URI,
            at=authored_at(),
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# add_status_to_participant_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_add_status_to_participant_returns_add(sample_participant_status):
    result = add_status_to_participant_activity(
        status=sample_participant_status,
        participant=_PARTICIPANT_URI,
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert isinstance(result, as_Add)


def test_add_status_to_participant_object_is_status(sample_participant_status):
    result = add_status_to_participant_activity(
        status=sample_participant_status,
        participant=_PARTICIPANT_URI,
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert result.object_ == sample_participant_status


@pytest.mark.spec("VAM-08-004")
def test_add_status_to_participant_targets_its_status_history(
    sample_participant_status,
):
    """ADR-0204: the target is <participant>/statuses, the context the case."""
    result = add_status_to_participant_activity(
        status=sample_participant_status,
        participant=_PARTICIPANT_URI,
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert result.target == f"{_PARTICIPANT_URI}/statuses"
    assert result.context == _CASE_URI


def test_add_status_to_participant_names_a_whole_participants_history(
    sample_participant, sample_participant_status
):
    """A participant passed whole is named by its id in the history."""
    result = add_status_to_participant_activity(
        status=sample_participant_status,
        participant=sample_participant,
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert result.target == f"{sample_participant.id_}/statuses"


def test_add_status_to_participant_keeps_an_explicit_context(
    sample_participant_status,
):
    """An explicit ``context`` wins over the status's own; the parse edge,
    not the factory, refuses one that disagrees (HP-08-015)."""
    explicit = "https://example.org/cases/explicit"
    result = add_status_to_participant_activity(
        status=sample_participant_status,
        participant=_PARTICIPANT_URI,
        actor=_ACTOR_URI,
        context=explicit,
        at=authored_at(),
    )
    assert result.context == explicit


def test_add_status_to_participant_defaults_context_to_the_statuss_case(
    sample_participant_status,
):
    result = add_status_to_participant_activity(
        status=sample_participant_status,
        participant=_PARTICIPANT_URI,
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert result.context == sample_participant_status.context


def test_add_status_to_participant_without_a_participant_raises(
    sample_participant_status,
):
    with pytest.raises(VultronActivityConstructionError):
        add_status_to_participant_activity(
            status=sample_participant_status,
            participant="",
            actor=_ACTOR_URI,
            at=authored_at(),
        )


@pytest.mark.spec("AF-04-001")
def test_add_status_to_participant_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        add_status_to_participant_activity(
            status="not-a-status",  # type: ignore[arg-type]
            participant=_PARTICIPANT_URI,
            context=_CASE_URI,
            at=authored_at(),
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# remove_participant_activity, reinstate_participant_activity (ADR-0199)
# ---------------------------------------------------------------------------

_REMOVED_URI = "https://example.org/actors/bob"


@pytest.mark.spec("AF-01-002")
@pytest.mark.spec("VAM-06-006")
def test_remove_participant_is_a_remove_of_the_actor_from_the_case():
    result = remove_participant_activity(
        _REMOVED_URI, _CASE_URI, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Remove)
    # The actor as a typed reference, not its participant record.
    dumped = result.model_dump(by_alias=True, mode="json", exclude_none=True)
    assert dumped["object"] == {"id": _REMOVED_URI, "type": "Actor"}
    assert dumped["origin"] == _CASE_URI
    assert "target" not in dumped
    assert dumped["context"] == _CASE_URI


@pytest.mark.spec("AF-01-002")
@pytest.mark.spec("VAM-06-007")
def test_reinstate_participant_is_an_add_of_the_actor_to_the_case():
    result = reinstate_participant_activity(
        _REMOVED_URI, _CASE_URI, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Add)
    dumped = result.model_dump(by_alias=True, mode="json", exclude_none=True)
    assert dumped["object"] == {"id": _REMOVED_URI, "type": "Actor"}
    assert dumped["target"] == _CASE_URI
    assert dumped["context"] == _CASE_URI


@pytest.mark.spec("AF-04-001")
@pytest.mark.parametrize(
    "build", [remove_participant_activity, reinstate_participant_activity]
)
def test_a_move_naming_no_case_raises(build):
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        build(_REMOVED_URI, None, actor=_ACTOR_URI, at=authored_at())
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# announce_admitted_act_activity (ADR-0199, ADR-0204)
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
@pytest.mark.spec("VAM-06-008")
def test_announce_carries_the_act_and_names_it_in_reply_to():
    removal = remove_participant_activity(
        _REMOVED_URI, _CASE_URI, actor=_ACTOR_URI, at=authored_at()
    )

    result = announce_admitted_act_activity(
        removal,
        _CASE_URI,
        actor="https://example.org/actors/case-manager",
        to=[_REMOVED_URI],
        at=authored_at(),
    )

    assert isinstance(result, as_Announce)
    assert _as_id(result.object_) == removal.id_
    assert result.in_reply_to == removal.id_
    assert result.context == _CASE_URI
    assert result.attributed_to is None


@pytest.mark.spec("AF-04-001")
def test_announce_of_no_act_raises():
    with pytest.raises(VultronActivityConstructionError):
        announce_admitted_act_activity(
            "not-an-activity",  # type: ignore[arg-type]
            _CASE_URI,
            at=authored_at(),
        )


# ---------------------------------------------------------------------------
# __init__.py re-exports (AF-04-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-04-002")
def test_all_case_participant_factories_importable_from_package():
    from vultron.wire.as2.factories import (  # noqa: F401
        add_participant_to_case_activity,
        add_status_to_participant_activity,
        announce_admitted_act_activity,
        reinstate_participant_activity,
        remove_participant_activity,
    )


@pytest.mark.spec("VAM-06-008")
@pytest.mark.spec("AF-04-001")
@pytest.mark.parametrize(
    "fields",
    [
        {"case": None},
        {"in_reply_to": "https://example.org/activities/other"},
    ],
    ids=["no-case", "mismatched-reply"],
)
def test_the_announce_refuses_a_missing_case_or_a_mismatched_reply(fields):
    """The CASE_MANAGER's own Announce names its case and the act it carries."""
    removal = remove_participant_activity(
        _REMOVED_URI, _CASE_URI, actor=_ACTOR_URI, at=authored_at()
    )
    case = fields.pop("case", _CASE_URI)

    with pytest.raises(VultronActivityConstructionError):
        announce_admitted_act_activity(
            removal, case, actor=_ACTOR_URI, at=authored_at(), **fields
        )
