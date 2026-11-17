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
"""A previewed case reference through the inbox run (MV-10-011, ADR-0205).

The stub Invite's ``object`` is a case reference carrying the case's
preview, and it is read as received: the receiver dispatches it as the stub
Invite, fetches nothing for it, and seeds or updates no case replica from
it, whether or not the receiver holds the case.  A CASE_MANAGER holding the
case reads an ``Accept`` of the stub Invite as the stub answer.
"""

from typing import Any

import pytest

from test.adapters.driving.fastapi.test_inbox_dereference import (
    _POSITION,
    _PUBLISHED,
    _REPLICA,
    _FakeFetcher,
    _fetches,
    _replica,
    _run,
    clear_actor_locks,  # noqa: F401  # autouse fixture
    no_outbox_drain,  # noqa: F401  # autouse fixture
)
from test.adapters.driving.fastapi.test_typed_reference_receipt import (
    _recording_dispatcher,
)
from test.support.case_manager import (
    CASE_MANAGER_ID,
    make_case_with_case_manager,
)
from test.support.signing import signed_body
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_preview import PreviewedCaseReference
from vultron.core.models.events import MessageSemantics, VultronEvent

_CASE_ID = "https://example.org/cases/previewed-1"


_SUMMARY = "A remote code execution vulnerability."
_INVITE_ID = "https://example.org/activities/stub-invite-1"


def _stub_invite_fields(case_id: str) -> dict[str, Any]:
    """The stub Invite, ``Invite(<case preview>)[target=<invitee>]``."""
    return {
        "type": "Invite",
        "id": _INVITE_ID,
        "published": _PUBLISHED,
        "actor": CASE_MANAGER_ID,
        "object": {
            "id": case_id,
            "type": "VulnerabilityCase",
            "preview": {
                "type": "CasePreview",
                "id": "https://example.org/previews/stub-invite-1",
                "summary": _SUMMARY,
            },
        },
        "target": {"id": _REPLICA, "type": "Organization"},
        "context": case_id,
        "to": [_REPLICA],
        # Every case activity states its sender's ledger tail (SYNC-18-015).
        "ledgerPosition": _POSITION,
    }


def _stub_invite(case_id: str) -> dict[str, Any]:
    """The stub Invite as the CASE_MANAGER delivers it to the invitee."""
    return signed_body(_stub_invite_fields(case_id))


def _stub_accept(case_id: str) -> dict[str, Any]:
    """The invitee's ``Accept`` of the stub Invite, embedding it inline."""
    invite = _stub_invite_fields(case_id)
    return signed_body(
        {
            "type": "Accept",
            "id": "https://example.org/activities/stub-accept-1",
            "published": _PUBLISHED,
            "actor": _REPLICA,
            "object": invite,
            "inReplyTo": _INVITE_ID,
            "to": [CASE_MANAGER_ID],
        }
    )


def _case_dump(dl: SqliteDataLayer, case_id: str) -> dict[str, Any] | None:
    case = dl.read(case_id)
    if case is None:
        return None
    assert isinstance(case, VulnerabilityCase)
    return case.model_dump(mode="json")


@pytest.mark.spec("MV-10-013")
@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("AKM-05-007")
@pytest.mark.spec("PCR-02-003")
def test_an_invitee_fetches_nothing_and_seeds_no_replica_from_a_preview():
    """The invitee holds no case: the preview is all it reads, so nothing is
    fetched, the activity is not unresolvable, and no case is stored."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_REPLICA)
    fetcher = _FakeFetcher({})
    dispatcher, seen = _recording_dispatcher()

    _run(dl, _REPLICA, _stub_invite(_CASE_ID), fetcher, dispatcher)

    assert fetcher.asked == []
    assert _fetches(dl) == []
    assert dl.read(_CASE_ID) is None
    _assert_read_as_a_reference(seen, _CASE_ID)


def _assert_read_as_a_reference(
    seen: list[VultronEvent], case_id: str
) -> None:
    """The one event is the stub Invite, naming the case by id as a
    reference carrying the preview: neither unresolvable (which would fetch)
    nor built into a case."""
    (event,) = seen
    assert event.semantic_type is MessageSemantics.INVITE_ACTOR_TO_CASE
    assert isinstance(event.object_, PreviewedCaseReference)
    assert not isinstance(event.object_, VulnerabilityCase)
    assert event.object_.id_ == case_id
    assert event.object_.preview.summary == _SUMMARY
    assert event.target_id == _REPLICA


@pytest.mark.spec("MV-10-013")
@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("PCR-02-004")
def test_a_preview_of_a_held_case_leaves_the_replica_unchanged():
    """A replica holding the case is not updated from a preview of it, and
    the preview is never handed to a handler as the case."""
    dl, case = _replica()
    before = _case_dump(dl, case.id_)
    fetcher = _FakeFetcher({})
    dispatcher, seen = _recording_dispatcher()

    _run(dl, _REPLICA, _stub_invite(case.id_), fetcher, dispatcher)

    assert fetcher.asked == []
    assert _fetches(dl) == []
    assert before is not None
    assert _case_dump(dl, case.id_) == before
    _assert_read_as_a_reference(seen, case.id_)


@pytest.mark.spec("MV-10-013")
@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("CM-11-003")
def test_a_case_manager_holding_the_case_reads_an_accept_of_the_stub_invite_as_the_stub_answer():
    """A CASE_MANAGER holding the case reads the embedded Invite's previewed
    reference as received, so the reply is the stub answer, not an answer
    to the full-case Invite, and nothing is fetched (ADR-0205)."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_MANAGER_ID)
    case = make_case_with_case_manager(dl)
    before = _case_dump(dl, case.id_)
    fetcher = _FakeFetcher({})
    dispatcher, seen = _recording_dispatcher()

    _run(dl, CASE_MANAGER_ID, _stub_accept(case.id_), fetcher, dispatcher)

    assert fetcher.asked == []
    assert _fetches(dl) == []
    assert _case_dump(dl, case.id_) == before
    (event,) = seen
    assert event.semantic_type is (
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE
    )
    assert event.case_id == case.id_
    assert event.invite_id == _INVITE_ID
    assert isinstance(event.inner_object, PreviewedCaseReference)
