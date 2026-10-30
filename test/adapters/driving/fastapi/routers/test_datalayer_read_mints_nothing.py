#!/usr/bin/env python
"""A DataLayer GET serves the stored object; it mints no id and reads no clock.

A demo recording (#3901) is a seeded run: :func:`deterministic_run` replaces
the id source and the clock, so one scenario gives the same ids every time.
A read that drew from either would shift every id minted after it, so adding
or removing a poll would change a recording with no change in protocol
behaviour (#5510).
"""

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

import uuid
from collections.abc import Callable, Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import (
    get_datalayer,
    reset_datalayer,
)
from vultron.adapters.driving.fastapi.main import app
from vultron.core.models import _helpers
from vultron.core.models.base import CoreObject
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.datalayer import DataLayer
from vultron.demo.determinism import deterministic_run
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

ACTOR_SEGMENT = "read-mints-nothing"
ACTOR_ID = canonical_actor_uri(ACTOR_SEGMENT)
READS = 5


@pytest.fixture
def datalayer() -> Iterator[DataLayer]:
    reset_datalayer(ACTOR_ID)
    dl = get_datalayer(ACTOR_ID, db_url="sqlite:///:memory:")
    dl.clear_all()
    dl.create(as_Service(id_=ACTOR_ID, name="Read Mints Nothing"))
    yield dl
    dl.clear_all()
    reset_datalayer(ACTOR_ID)


@pytest.fixture
def client(datalayer: DataLayer) -> TestClient:
    """A client with no lifespan.

    The lifespan starts background work (the outbox monitor, the ledger
    position statement) that mints node ids on its own threads, so a count
    taken while it runs would not be the reads' alone.
    """
    return TestClient(app)


@pytest.fixture
def stored(datalayer: DataLayer) -> dict[str, str]:
    """One stored object of each kind a demo reads back, keyed by type."""
    report = as_VulnerabilityReport(name="Report", content="content")
    case = as_VulnerabilityCase(
        name="Case",
        vulnerability_reports=[report.id_],
        attributed_to=ACTOR_ID,
    )
    participant = as_CaseParticipant(attributed_to=ACTOR_ID, context=case.id_)
    for obj in (report, case, participant):
        datalayer.create(obj)
    return {
        "Service": ACTOR_ID,
        "VulnerabilityReport": report.id_,
        "VulnerabilityCase": case.id_,
        "CaseParticipant": participant.id_,
    }


def _by_key(object_type: str, object_id: str) -> str:
    return f"/api/v2/actors/{ACTOR_SEGMENT}/datalayer/{object_id}"


def _by_type_and_id(object_type: str, object_id: str) -> str:
    return (
        f"/api/v2/actors/{ACTOR_SEGMENT}/datalayer/{object_type}/{object_id}"
    )


#: The type-and-id route takes an id with no ``/``, so the actor (whose id is
#: an http URI) is read only by key.
_URN_TYPES = ["VulnerabilityReport", "VulnerabilityCase", "CaseParticipant"]
_READS = [(_by_key, t) for t in ["Service", *_URN_TYPES]] + [
    (_by_type_and_id, t) for t in _URN_TYPES
]


_Params = dict[str, str | list[str]]


def _draws_after(
    client: TestClient,
    path: str,
    reads: int,
    params: _Params | None = None,
) -> tuple[list[uuid.UUID], datetime]:
    """The ids and the time a seeded run mints after *reads* GETs of *path*."""
    with deterministic_run("datalayer-read"):
        for _ in range(reads):
            response = client.get(path, params=params)
            assert response.status_code == 200, response.text
        return [uuid.uuid4() for _ in range(3)], _helpers.now_utc()


@pytest.mark.parametrize(("route", "object_type"), _READS)
def test_get_object_mints_no_id_and_reads_no_clock(
    client: TestClient,
    stored: dict[str, str],
    route: Callable[[str, str], str],
    object_type: str,
) -> None:
    path = route(object_type, stored[object_type])

    assert _draws_after(client, path, READS) == _draws_after(client, path, 0)


@pytest.fixture
def offers(datalayer: DataLayer, stored: dict[str, str]) -> list[str]:
    """Offers the actor sent, carrying each stored kind of object."""
    ids = []
    for object_type in _URN_TYPES:
        held = datalayer.read(stored[object_type])
        assert isinstance(held, CoreObject)
        offer = as_Offer(
            actor=ACTOR_ID, object_=held, to=["https://example.org/actors/b"]
        )
        datalayer.create(offer)
        ids.append(offer.id_)
    return ids


def test_other_read_routes_mint_no_id_and_read_no_clock(
    client: TestClient, stored: dict[str, str], offers: list[str]
) -> None:
    """Every other read route a demo or harness polls draws nothing either."""
    base = f"/api/v2/actors/{ACTOR_SEGMENT}/datalayer"
    reads: list[tuple[str, _Params | None]] = [
        *[(f"{base}/Offers/{offer_id}", None) for offer_id in offers],
        *[
            (f"{base}/Offer/", _Params(object_id=offer_id))
            for offer_id in offers
        ],
        (f"{base}/Report/", {"id": stored["VulnerabilityReport"]}),
        (f"{base}/Offers/", None),
        (f"{base}/Reports/", None),
        (f"{base}/Actors/", None),
        (f"{base}/outbox/", None),
        (f"{base}/CaseParticipants/", None),
        (f"{base}/", None),
        (f"{base}/", {"type": ["CaseParticipant", "VulnerabilityCase"]}),
    ]
    for path, params in reads:
        assert _draws_after(client, path, READS, params) == _draws_after(
            client, path, 0, params
        ), (path, params)


def test_get_report_serves_the_stored_report(
    client: TestClient, datalayer: DataLayer, stored: dict[str, str]
) -> None:
    held = datalayer.read(stored["VulnerabilityReport"])
    assert held is not None

    response = client.get(
        f"/api/v2/actors/{ACTOR_SEGMENT}/datalayer/Report/",
        params={"id": held.id_},
    )

    assert response.json() == held.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )


def test_get_report_refuses_an_object_that_is_not_a_report(
    client: TestClient, stored: dict[str, str]
) -> None:
    response = client.get(
        f"/api/v2/actors/{ACTOR_SEGMENT}/datalayer/Report/",
        params={"id": stored["VulnerabilityCase"]},
    )

    assert response.status_code == 404


@pytest.mark.parametrize(("route", "object_type"), _READS)
def test_get_object_serves_the_stored_object(
    client: TestClient,
    datalayer: DataLayer,
    stored: dict[str, str],
    route: Callable[[str, str], str],
    object_type: str,
) -> None:
    """The body is the stored object's AS2 rendering, field for field."""
    held = datalayer.read(stored[object_type])
    assert held is not None

    response = client.get(route(object_type, stored[object_type]))

    assert response.headers["content-type"] == "application/activity+json"
    assert response.json() == held.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )


def test_camel_case_participant_dump_revalidates_without_minting() -> None:
    """A participant rebuilt from its AS2 dump keeps its statuses, minting none.

    The seed of an empty ``participant_statuses`` read only the field name,
    so an AS2 dump (``participantStatuses``) looked empty, and a status was
    built (an id and a clock read) before the alias overrode it.
    """
    participant = CaseParticipant(
        attributed_to="https://example.org/actors/a",
        context="https://example.org/cases/c",
    )
    dump = participant.model_dump(by_alias=True, serialize_as_any=True)

    def rebuild() -> tuple[CaseParticipant, uuid.UUID]:
        with deterministic_run("participant-rebuild"):
            rebuilt = CaseParticipant.model_validate(dump)
            return rebuilt, uuid.uuid4()

    def mint_only() -> uuid.UUID:
        with deterministic_run("participant-rebuild"):
            return uuid.uuid4()

    rebuilt, next_id = rebuild()

    assert rebuilt.participant_statuses == participant.participant_statuses
    assert next_id == mint_only()
