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
"""The case ledger's id is an identity only: no route serves it.

ADR-0204 names a case's ledger ``<case>/ledger`` so a commit can be an
``Add`` to it, and opens no fetch surface for it (IE-02-003; fetching the
ledger is separate work).  These tests pin that: no route is declared for a
ledger, and the case-object fetch, the one route that serves what a case
names, answers 404 for it even to an active participant.
"""

from collections.abc import Iterator

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from test.support.case_manager import make_case_with_case_manager
from test.support.objects import make
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    get_datalayer,
    reset_datalayer,
)
from vultron.adapters.driven.http_object_fetch import REQUESTER_HEADER
from vultron.adapters.driving.fastapi.app import app_v2
from vultron.adapters.utils import strip_id_prefix
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import case_ledger_id
from vultron.core.models.case_participant import CaseParticipant

_SLUG = "case-actor"
_PARTICIPANT = "https://example.org/actors/vendor"


@pytest.fixture
def host() -> Iterator[tuple[SqliteDataLayer, VulnerabilityCase]]:
    """The case host's store: a case it manages, with one participant."""
    host_id = canonical_actor_uri(_SLUG)
    reset_datalayer(host_id)
    dl = get_datalayer(host_id, db_url="sqlite:///:memory:")
    case = make_case_with_case_manager(dl, host_id)
    participant = make(
        CaseParticipant, attributed_to=_PARTICIPANT, context=case.id_
    )
    case.add_participant(participant)
    dl.save(case)
    dl.create(participant)
    yield dl, case
    reset_datalayer(host_id)


@pytest.mark.spec("SYNC-02-006")
@pytest.mark.spec("IE-02-003")
def test_no_route_is_declared_for_a_ledger() -> None:
    paths = app_v2.openapi()["paths"]
    assert paths, "the app declares no routes; the check would be vacuous"
    ledger_routes = [
        path for path in paths if "ledger" in path.strip("/").split("/")
    ]
    assert ledger_routes == []


@pytest.mark.spec("SYNC-02-006")
@pytest.mark.spec("IE-02-003")
def test_the_case_object_fetch_does_not_serve_the_ledger(
    client_actors: TestClient, host
) -> None:
    _, case = host

    response = client_actors.get(
        f"/actors/{_SLUG}/cases/{strip_id_prefix(case.id_)}/objects",
        params={"object_id": case_ledger_id(case.id_)},
        headers={REQUESTER_HEADER: _PARTICIPANT},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
