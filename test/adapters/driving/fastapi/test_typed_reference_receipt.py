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
"""A typed reference through the inbox run (MV-10-011, AKM-05-007).

An activity whose ``object`` is a typed reference is handled with the object
the receiver holds; one the receiver lacks waits on its fetch and is replayed
with the fetched object; and a failed fetch leaves it to the path that needs
the object.  No handler is ever given the reference as the object.
"""

from typing import Any
from unittest.mock import Mock

import pytest

from test.adapters.driving.fastapi.test_inbox_dereference import (
    _POSITION,
    _PUBLISHED,
    _REPLICA,
    _body,
    _embargo,
    _FakeFetcher,
    _fetches,
    _held,
    _replica,
    _run,
    clear_actor_locks,  # noqa: F401  # autouse fixture
    no_outbox_drain,  # noqa: F401  # autouse fixture
)
from test.support.case_manager import CASE_MANAGER_ID
from test.support.signing import signed_body
from vultron.adapters.driven.http_object_fetch import ObjectFetchResult
from vultron.core.models.case_participant.participant import CaseParticipant
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events import MessageSemantics, VultronEvent
from vultron.core.models.object_fetch import (
    ObjectFetchSource,
    ObjectFetchUse,
    ObjectReference,
)
from vultron.core.models.use_case_result import HandlerResult


def _recording_dispatcher() -> tuple[Mock, list[VultronEvent]]:
    seen: list[VultronEvent] = []

    def _record(event: VultronEvent, _dl: Any) -> HandlerResult:
        seen.append(event)
        return HandlerResult.applied()

    dispatcher = Mock()
    dispatcher.dispatch.side_effect = _record
    return dispatcher, seen


def _referencing_accept(
    case_id: str, object_id: str, type_: str
) -> dict[str, Any]:
    """An ``Accept`` whose ``object`` is a typed reference."""
    return signed_body(
        {
            "type": "Accept",
            "id": "https://example.org/activities/accept-ref-1",
            "published": _PUBLISHED,
            "actor": CASE_MANAGER_ID,
            "object": {"id": object_id, "type": type_},
            "context": case_id,
            "to": [_REPLICA],
            "ledgerPosition": _POSITION,
        }
    )


@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("AKM-05-018")
def test_a_reference_to_a_held_participant_is_handled_with_the_held_record():
    """``Remove({id, type: CaseParticipant})`` routes as a Remove of that
    participant, and the handler reads the participant the receiver holds,
    not a hollow one with an invented status (#5265)."""
    dl, case = _replica()
    (participant_id,) = case.case_participants
    assert isinstance(participant_id, str)
    held = dl.read(participant_id)
    assert isinstance(held, CaseParticipant)
    payload = signed_body(
        {
            "type": "Remove",
            "id": "https://example.org/activities/remove-ref-1",
            "published": _PUBLISHED,
            "actor": CASE_MANAGER_ID,
            "object": {"id": participant_id, "type": "CaseParticipant"},
            "target": case.id_,
            "context": case.id_,
            "to": [_REPLICA],
            "ledgerPosition": _POSITION,
        }
    )
    fetcher = _FakeFetcher({})
    dispatcher, seen = _recording_dispatcher()

    _run(dl, _REPLICA, payload, fetcher, dispatcher)

    (event,) = seen
    assert (
        event.semantic_type
        is MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE
    )
    assert isinstance(event.object_, CaseParticipant)
    # The held record's roles and author, which a hollow reference lacks.
    assert held.case_roles
    assert event.object_.case_roles == held.case_roles
    assert event.object_.attributed_to == held.attributed_to
    assert fetcher.asked == []


@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("AKM-05-007")
@pytest.mark.spec("AKM-05-010")
def test_a_reference_to_an_object_the_receiver_lacks_is_fetched_first():
    """The activity waits on the fetch of the object the reference names, and
    its replay is handled with the fetched object."""
    dl, case = _replica()
    embargo = _embargo(case.id_)
    payload = _referencing_accept(case.id_, embargo.id_, "EmbargoEvent")
    fetcher = _FakeFetcher(
        {embargo.id_: ObjectFetchResult(_body(embargo), None, 1)}
    )
    dispatcher, seen = _recording_dispatcher()

    _run(dl, _REPLICA, payload, fetcher, dispatcher)

    assert fetcher.asked == [
        (
            ObjectReference(
                object_id=embargo.id_,
                source=ObjectFetchSource.CASE_HOST,
                host_actor_id=CASE_MANAGER_ID,
                case_id=case.id_,
                use=ObjectFetchUse.STORE,
            ),
            _REPLICA,
        )
    ]
    (event,) = seen
    assert isinstance(event.object_, EmbargoEvent)
    assert event.object_.end_time == embargo.end_time
    assert _fetches(dl) == []
    assert not _held(dl, payload["id"])


@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("AKM-05-015")
@pytest.mark.parametrize(
    "type_", ["EmbargoEvent", "Note", "CaseParticipant", "VulnerabilityReport"]
)
def test_a_reference_whose_fetch_fails_goes_on_as_its_bare_id(type_: str):
    """After a failed fetch the activity is handled as one naming the object
    by URI: the path that needs the object refuses it, and no handler is
    given the reference, or a hollow object staged from it, in its place."""
    dl, case = _replica()
    missing = "urn:uuid:nobody-holds-this"
    payload = _referencing_accept(case.id_, missing, type_)
    fetcher = _FakeFetcher(
        {missing: ObjectFetchResult(None, "GET … answered HTTP 404", 1)}
    )
    dispatcher, seen = _recording_dispatcher()

    _run(dl, _REPLICA, payload, fetcher, dispatcher)

    (event,) = seen
    assert event.semantic_type is MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
    assert getattr(event, "unresolved_object_id", None) == missing
    assert _fetches(dl) == []
    assert not _held(dl, payload["id"])
