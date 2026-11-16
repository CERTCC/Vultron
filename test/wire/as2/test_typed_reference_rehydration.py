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
"""A typed reference is never read as the object (MV-10-011, ADR-0198).

Rehydration puts the object the receiver holds in a reference's place, or
reduces a reference to an object it does not hold to its bare id, so the inbox
fetches the object before any handler reads it (AKM-05-007).  A stored
reference reads back as one, never as a hollow object of its type.
"""

import logging
from typing import Any

import pytest

from test.support.case_manager import (
    CASE_MANAGER_ID,
    make_case_with_case_manager,
)
from test.support.received import TEST_SENDER_POSITION
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.db_record import (
    object_to_record,
    record_to_object,
)
from vultron.core.models.case_participant.participant import CaseParticipant
from vultron.wire.as2.extractor._pattern import bare_object_id
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.rehydration import rehydrate
from vultron.wire.as2.typed_reference import as_TypedReference
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)

_PUBLISHED = "2026-10-26T12:00:00Z"
_RECEIVER = "https://example.org/actors/vendor"


def _remove(case_id: str, reference: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Remove",
        "id": "https://example.org/activities/remove-1",
        "published": _PUBLISHED,
        "actor": CASE_MANAGER_ID,
        "object": reference,
        "target": case_id,
        "context": case_id,
        "ledgerPosition": TEST_SENDER_POSITION.model_dump(by_alias=True),
    }


def _undo(inner: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Undo",
        "id": "https://example.org/activities/undo-1",
        "published": _PUBLISHED,
        "actor": CASE_MANAGER_ID,
        "object": inner,
        "ledgerPosition": TEST_SENDER_POSITION.model_dump(by_alias=True),
    }


@pytest.fixture
def held() -> tuple[SqliteDataLayer, str, CaseParticipant]:
    """A receiver's store holding a case and its one participant."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    case = make_case_with_case_manager(dl)
    (participant_id,) = case.case_participants
    assert isinstance(participant_id, str)
    participant = dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    return dl, case.id_, participant


@pytest.mark.spec("MV-10-011")
def test_a_reference_to_a_held_object_is_replaced_by_it(
    held: tuple[SqliteDataLayer, str, CaseParticipant],
) -> None:
    dl, case_id, participant = held
    activity = parse_activity(
        _remove(case_id, {"id": participant.id_, "type": "CaseParticipant"})
    )

    rehydrated = rehydrate(activity, dl=dl)

    assert isinstance(rehydrated, as_TransitiveActivity)
    assert isinstance(rehydrated.object_, CaseParticipant)
    assert rehydrated.object_.case_roles == participant.case_roles


@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("AKM-05-007")
def test_a_reference_to_an_object_not_held_goes_on_as_its_bare_id(
    held: tuple[SqliteDataLayer, str, CaseParticipant],
) -> None:
    dl, case_id, _ = held
    missing = "https://example.org/participants/not-held"
    activity = parse_activity(
        _remove(case_id, {"id": missing, "type": "CaseParticipant"})
    )

    rehydrated = rehydrate(activity, dl=dl)

    assert isinstance(rehydrated, as_TransitiveActivity)
    assert rehydrated.object_ == missing
    assert bare_object_id(rehydrated) == missing


@pytest.mark.spec("MV-10-011")
def test_a_reference_to_an_object_of_another_type_is_not_read_as_it(
    held: tuple[SqliteDataLayer, str, CaseParticipant],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A held object that is not the type the reference names is not the
    object it names: the reference goes on as its bare id."""
    dl, case_id, participant = held
    activity = parse_activity(
        _remove(case_id, {"id": participant.id_, "type": "EmbargoEvent"})
    )

    with caplog.at_level(logging.WARNING):
        rehydrated = rehydrate(activity, dl=dl)

    assert isinstance(rehydrated, as_TransitiveActivity)
    assert rehydrated.object_ == participant.id_
    assert any(
        "MV-10-011" in r.getMessage() and participant.id_ in r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING
    )


@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("VAM-01-009")
def test_a_nested_reference_not_held_ends_the_chain_as_its_bare_id(
    held: tuple[SqliteDataLayer, str, CaseParticipant],
) -> None:
    dl, case_id, _ = held
    missing = "https://example.org/participants/not-held"
    activity = parse_activity(
        _undo(_remove(case_id, {"id": missing, "type": "CaseParticipant"}))
    )

    rehydrated = rehydrate(activity, dl=dl)

    assert isinstance(rehydrated, as_TransitiveActivity)
    assert bare_object_id(rehydrated) == missing
    inner = rehydrated.object_
    assert isinstance(inner, as_TransitiveActivity)
    assert inner.object_ == missing


@pytest.mark.spec("MV-10-011")
def test_a_stored_reference_reads_back_as_a_reference(
    held: tuple[SqliteDataLayer, str, CaseParticipant],
) -> None:
    """A reference kept inline in a stored activity is never rebuilt as a
    hollow object of its type, with that class's defaults (#5265)."""
    _, case_id, _ = held
    reference = {
        "id": "https://example.org/participants/p1",
        "type": "CaseParticipant",
    }
    activity = parse_activity(_undo(_remove(case_id, reference)))

    read_back = record_to_object(object_to_record(activity))

    inner = getattr(read_back, "object_", None)
    assert isinstance(inner, as_TransitiveActivity)
    assert isinstance(inner.object_, as_TypedReference)
    assert inner.object_.id_ == reference["id"]
