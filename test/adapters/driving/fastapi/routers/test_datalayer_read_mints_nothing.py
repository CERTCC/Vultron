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

import json
import uuid
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import (
    get_datalayer,
    reset_datalayer,
)
from vultron.adapters.driving.fastapi.main import app
from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.adapters.driving.fastapi.routers.datalayer import _serve_stored
from vultron.core.models import _helpers
from vultron.core.models.base import CoreObject
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.ports.datalayer import DataLayer
from vultron.demo.determinism import deterministic_run
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.examples.participant import accept_invite_to_case
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
_SERVICE = as_Service(id_=ACTOR_ID, name="Read Mints Nothing")

#: Anything that renders as an AS2 document.
_AS2Object = as_Base | CoreObject


@pytest.fixture
def datalayer() -> Iterator[DataLayer]:
    reset_datalayer(ACTOR_ID)
    dl = get_datalayer(ACTOR_ID, db_url="sqlite:///:memory:")
    dl.clear_all()
    dl.create(_SERVICE)
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
def built() -> dict[str, _AS2Object]:
    """One object of each kind a demo reads back, keyed by type, as built."""
    report = as_VulnerabilityReport(name="Report", content="content")
    case = as_VulnerabilityCase(
        name="Case",
        vulnerability_reports=[report.id_],
        attributed_to=ACTOR_ID,
    )
    participant = as_CaseParticipant(attributed_to=ACTOR_ID, context=case.id_)
    return {
        "Service": _SERVICE,
        "VulnerabilityReport": report,
        "VulnerabilityCase": case,
        "CaseParticipant": participant,
    }


@pytest.fixture
def stored(
    datalayer: DataLayer, built: dict[str, _AS2Object]
) -> dict[str, str]:
    """The ids of *built*, each stored (the Service by the datalayer fixture)."""
    for object_type, obj in built.items():
        if object_type != "Service":
            datalayer.create(obj)
    return {object_type: obj.id_ for object_type, obj in built.items()}


def _as2_body(obj: _AS2Object) -> dict[str, Any]:
    """The AS2 document *obj* renders as, built from the object itself."""
    return obj.model_dump(mode="json", by_alias=True, exclude_none=True)


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
    client: TestClient, built: dict[str, _AS2Object], stored: dict[str, str]
) -> None:
    response = client.get(
        f"/api/v2/actors/{ACTOR_SEGMENT}/datalayer/Report/",
        params={"id": stored["VulnerabilityReport"]},
    )

    assert response.status_code == 200
    assert response.json() == _as2_body(built["VulnerabilityReport"])


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
    built: dict[str, _AS2Object],
    stored: dict[str, str],
    route: Callable[[str, str], str],
    object_type: str,
) -> None:
    """The body is the AS2 rendering of the object as built, field for field."""
    response = client.get(route(object_type, stored[object_type]))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/activity+json"
    assert response.json() == _as2_body(built[object_type])


@pytest.mark.parametrize("route", [_by_key, _by_type_and_id])
def test_an_activity_is_served_with_its_full_inline_object(
    client: TestClient,
    datalayer: DataLayer,
    route: Callable[[str, str], str],
) -> None:
    """A stored ``Accept(Invite)`` is served with the whole Invite it holds.

    The old rebuild narrowed a semantic activity to its base wire class, so
    the inline Invite lost its ``actor``, ``object`` and ``target`` (#5510).
    """
    accept = accept_invite_to_case()
    datalayer.create(accept)

    response = client.get(route("Accept", accept.id_))

    assert response.status_code == 200
    body = response.json()
    assert body == _as2_body(accept)
    invite = body["object"]
    assert invite["type"] == "Invite"
    assert invite["actor"] == "https://vultron.example/organizations/vendorco"
    assert invite["object"]["id"] == (
        "https://vultron.example/organizations/coordinator"
    )
    assert invite["target"]["type"] == "VulnerabilityCaseStub"


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


def test_a_bookkeeping_row_is_served_as_its_plain_dump() -> None:
    """A row with no AS2 form is served as its dump, not as AS2 (ARCH-20-006).

    Called directly: a bookkeeping row's id holds a ``/``, so no by-id route
    path reaches it as one key.
    """
    record = VultronOfferRecord(
        offer_id="urn:uuid:offer-1",
        offer_actor_id=ACTOR_ID,
        report_id="urn:uuid:report-1",
    )

    served = _serve_stored(record)

    assert not isinstance(served, AS2JSONResponse)
    assert isinstance(served, dict)
    assert served["type"] == "OfferRecord"
    assert served["offer_id"] == "urn:uuid:offer-1"
    assert served["offer_actor_id"] == ACTOR_ID
    assert served["report_id"] == "urn:uuid:report-1"


def test_an_as2_object_is_served_as_an_as2_document() -> None:
    report = as_VulnerabilityReport(name="Report", content="content")

    assert report.published is not None and report.updated is not None

    served = _serve_stored(report)

    assert isinstance(served, AS2JSONResponse)
    assert served.media_type == "application/activity+json"
    assert json.loads(bytes(served.body)) == {
        "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
        "type": "VulnerabilityReport",
        "id": report.id_,
        "name": "Report",
        "content": "content",
        "published": report.published.isoformat(),
        "updated": report.updated.isoformat(),
    }
