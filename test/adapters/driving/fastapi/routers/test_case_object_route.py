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
"""The case host's object read, ``GET {actor}/case-object`` (AKM-05-006)."""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from test.adapters.driving.fastapi.routers.conftest import (
    _in_memory_actor_dl_override,
)
from test.support.case_manager import make_case_with_case_manager
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    get_datalayer,
    reset_datalayer,
)
from vultron.adapters.driven.http_object_fetch import REQUESTER_HEADER
from vultron.adapters.driving.fastapi.deps import get_actor_dl
from vultron.adapters.driving.fastapi.routers import actors as actors_router
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_event import EmbargoEvent

_SLUG = "case-actor"
_PARTICIPANT = "https://example.org/actors/vendor"
_OUTSIDER = "https://example.org/actors/outsider"


@pytest.fixture
def host() -> Iterator[tuple[SqliteDataLayer, VulnerabilityCase]]:
    """The case host's store: a case it manages, with one participant."""
    host_id = canonical_actor_uri(_SLUG)
    reset_datalayer(host_id)
    dl = get_datalayer(host_id, db_url="sqlite:///:memory:")
    case = make_case_with_case_manager(dl, host_id)
    participant = CaseParticipant(attributed_to=_PARTICIPANT, context=case.id_)
    case.add_participant(participant)
    dl.save(case)
    dl.create(participant)
    yield dl, case
    reset_datalayer(host_id)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(actors_router.router)
    app.dependency_overrides[get_actor_dl] = _in_memory_actor_dl_override()
    yield TestClient(app)
    app.dependency_overrides = {}


def _get(
    client: TestClient, case_id: str, object_id: str, requester: str | None
):
    headers = {REQUESTER_HEADER: requester} if requester else {}
    return client.get(
        f"/actors/{_SLUG}/case-object",
        params={"case_id": case_id, "object_id": object_id},
        headers=headers,
    )


@pytest.mark.spec("AKM-05-006")
def test_a_participant_gets_an_object_the_case_names(client, host):
    dl, case = host
    embargo = EmbargoEvent(
        context=case.id_, end_time=now_utc() + timedelta(days=30)
    )
    dl.save(embargo)

    response = _get(client, case.id_, embargo.id_, _PARTICIPANT)

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith(
        "application/activity+json"
    )
    body = response.json()
    assert body["id"] == embargo.id_
    assert body["type"] == "EmbargoEvent"


@pytest.mark.spec("AKM-05-006")
def test_a_non_participant_is_refused_with_403(client, host):
    _, case = host

    response = _get(client, case.id_, case.id_, _OUTSIDER)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.spec("AKM-05-006")
def test_a_request_naming_no_requester_is_refused_with_401(client, host):
    _, case = host

    response = _get(client, case.id_, case.id_, None)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.spec("AKM-05-006")
def test_an_object_the_case_does_not_name_is_404(client, host):
    _, case = host

    response = _get(client, case.id_, "urn:uuid:not-here", _PARTICIPANT)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.spec("AKM-05-006")
def test_a_case_the_host_does_not_hold_is_404(client, host):
    response = _get(
        client, "https://example.org/cases/unknown", "urn:uuid:x", _PARTICIPANT
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
