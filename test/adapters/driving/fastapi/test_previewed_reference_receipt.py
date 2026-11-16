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

An activity whose ``object`` is a case reference carrying the case's preview
is read as received: the receiver fetches nothing for it, and no case
replica is seeded or updated from it, whether or not the receiver holds the
case.
"""

from typing import Any

import pytest

from test.adapters.driving.fastapi.test_inbox_dereference import (
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
from test.support.case_manager import CASE_MANAGER_ID
from test.support.signing import signed_body
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events import MessageSemantics, VultronEvent

_CASE_ID = "https://example.org/cases/previewed-1"


def _stub_invite(case_id: str) -> dict[str, Any]:
    """An ``Invite`` whose object is the case's previewed reference."""
    return signed_body(
        {
            "type": "Invite",
            "id": "https://example.org/activities/stub-invite-1",
            "published": _PUBLISHED,
            "actor": CASE_MANAGER_ID,
            "object": {
                "id": case_id,
                "type": "VulnerabilityCase",
                "preview": {
                    "type": "VulnerabilityCaseStub",
                    "id": f"{case_id}/stub",
                    "caseId": case_id,
                    "summary": "A remote code execution vulnerability.",
                },
            },
            "target": _REPLICA,
            "to": [_REPLICA],
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
    """The one event names the case by id, as a reference: the preview is
    neither unresolvable (which would fetch) nor built into a case."""
    (event,) = seen
    assert event.semantic_type is MessageSemantics.UNKNOWN
    assert isinstance(event.object_, CoreObject)
    assert not isinstance(event.object_, VulnerabilityCase)
    assert event.object_.id_ == case_id


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
