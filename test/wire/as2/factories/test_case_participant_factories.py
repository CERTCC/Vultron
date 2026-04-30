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

from vultron.wire.as2.factories import (
    VultronActivityConstructionError,
    add_participant_to_case_activity,
    add_status_to_participant_activity,
    create_participant_activity,
    create_status_for_participant_activity,
    remove_participant_from_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Create,
    as_Remove,
)
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import ParticipantStatus

_ACTOR_URI = "https://example.org/actors/alice"
_CASE_URI = "https://example.org/cases/case-001"
_PARTICIPANT_URI = "https://example.org/participants/part-001"


@pytest.fixture
def sample_participant() -> CaseParticipant:
    return CaseParticipant(attributed_to=_ACTOR_URI)


@pytest.fixture
def sample_participant_status() -> ParticipantStatus:
    return ParticipantStatus(context=_CASE_URI)


# ---------------------------------------------------------------------------
# create_participant_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_create_participant_returns_create(sample_participant):
    result = create_participant_activity(
        participant=sample_participant, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Create)


def test_create_participant_object_is_participant(sample_participant):
    result = create_participant_activity(
        participant=sample_participant, actor=_ACTOR_URI
    )
    assert result.object_ == sample_participant


def test_create_participant_target_is_set(sample_participant):
    result = create_participant_activity(
        participant=sample_participant, target=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.target == _CASE_URI


def test_create_participant_auto_generates_name(sample_participant):
    """CreateParticipantActivity model_validator auto-generates a name."""
    result = create_participant_activity(
        participant=sample_participant, actor=_ACTOR_URI
    )
    assert result.name is not None
    assert "CaseParticipant" in result.name


def test_create_participant_explicit_name_preserved(sample_participant):
    """Explicitly provided name is not overwritten by the model validator."""
    result = create_participant_activity(
        participant=sample_participant, name="My Custom Name", actor=_ACTOR_URI
    )
    assert result.name == "My Custom Name"


@pytest.mark.spec("AF-04-001")
def test_create_participant_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        create_participant_activity(
            participant="not-a-participant"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# create_status_for_participant_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_create_status_for_participant_returns_create(
    sample_participant_status,
):
    result = create_status_for_participant_activity(
        status=sample_participant_status, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Create)


def test_create_status_for_participant_object_is_status(
    sample_participant_status,
):
    result = create_status_for_participant_activity(
        status=sample_participant_status, actor=_ACTOR_URI
    )
    assert result.object_ == sample_participant_status


def test_create_status_for_participant_target_is_set(
    sample_participant_status,
):
    result = create_status_for_participant_activity(
        status=sample_participant_status,
        target=_PARTICIPANT_URI,
        actor=_ACTOR_URI,
    )
    assert result.target == _PARTICIPANT_URI


@pytest.mark.spec("AF-04-001")
def test_create_status_for_participant_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        create_status_for_participant_activity(
            status="not-a-status"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# add_status_to_participant_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_add_status_to_participant_returns_add(sample_participant_status):
    result = add_status_to_participant_activity(
        status=sample_participant_status, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Add)


def test_add_status_to_participant_object_is_status(sample_participant_status):
    result = add_status_to_participant_activity(
        status=sample_participant_status, actor=_ACTOR_URI
    )
    assert result.object_ == sample_participant_status


def test_add_status_to_participant_target_is_set(sample_participant_status):
    result = add_status_to_participant_activity(
        status=sample_participant_status,
        target=_PARTICIPANT_URI,
        actor=_ACTOR_URI,
    )
    assert result.target == _PARTICIPANT_URI


@pytest.mark.spec("AF-04-001")
def test_add_status_to_participant_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        add_status_to_participant_activity(
            status="not-a-status"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# add_participant_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_add_participant_to_case_returns_add(sample_participant):
    result = add_participant_to_case_activity(
        participant=sample_participant, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Add)


def test_add_participant_to_case_object_is_participant(sample_participant):
    result = add_participant_to_case_activity(
        participant=sample_participant, actor=_ACTOR_URI
    )
    assert result.object_ == sample_participant


def test_add_participant_to_case_target_is_set(sample_participant):
    result = add_participant_to_case_activity(
        participant=sample_participant, target=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.target == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_add_participant_to_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        add_participant_to_case_activity(
            participant="not-a-participant"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# remove_participant_from_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_remove_participant_from_case_returns_remove(sample_participant):
    result = remove_participant_from_case_activity(
        participant=sample_participant, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Remove)


def test_remove_participant_from_case_object_is_participant(
    sample_participant,
):
    result = remove_participant_from_case_activity(
        participant=sample_participant, actor=_ACTOR_URI
    )
    assert result.object_ == sample_participant


def test_remove_participant_from_case_target_is_set(sample_participant):
    result = remove_participant_from_case_activity(
        participant=sample_participant, target=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.target == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_remove_participant_from_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        remove_participant_from_case_activity(
            participant="not-a-participant"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# __init__.py re-exports (AF-04-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-04-002")
def test_all_case_participant_factories_importable_from_package():
    from vultron.wire.as2.factories import (  # noqa: F401
        add_participant_to_case_activity,
        add_status_to_participant_activity,
        create_participant_activity,
        create_status_for_participant_activity,
        remove_participant_from_case_activity,
    )
