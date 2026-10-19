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

"""The Offer routes answer for a received Offer from its archive record.

A receiver holds a received activity only under the key it derives from the
activity's id, its ``ReceivedActivityRecord`` (DL-06-006).  Inbox ingress
still writes a row under the sender's id today; the follow-on inbox change
stops it.  Each route must answer the same with and without that row.
"""

import pytest
from fastapi import status

from test.support.received import archive_received
from vultron.adapters.driving.fastapi.inbox_storage import (
    _store_inbox_activity,
)
from vultron.wire.as2.factories import (
    rm_invite_to_case_activity,
    rm_submit_report_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

pytestmark = pytest.mark.spec("DL-06-006")

FINDER = "https://finder.example/actors/finder"
OFFER_UUID = "6c1b2d4e-8f7a-4b3c-9d2e-1a0f5e6d7c8b"
OFFER_ID = f"urn:uuid:{OFFER_UUID}"
REPORT_ID = "https://finder.example/reports/r-1"


def _received_offer(to: str):
    return rm_submit_report_activity(
        as_VulnerabilityReport(id_=REPORT_ID, name="r", content="c"),
        to=to,
        actor=FINDER,
        id_=OFFER_ID,
    )


@pytest.fixture
def receive(datalayer, dl_actor_id):
    """Deliver the finder's Offer to the actor, as intake archives it."""

    def _receive(*, ingress_row: bool):
        offer = _received_offer(dl_actor_id)
        if ingress_row:
            assert _store_inbox_activity(datalayer, offer)
        archive_received(datalayer, offer)
        return offer

    return _receive


def _routes(prefix: str) -> dict[str, tuple[str, dict]]:
    return {
        "get_actor_offer": (f"{prefix}/Offers/{OFFER_UUID}", {}),
        "get_offer": (f"{prefix}/Offer/", {"object_id": OFFER_ID}),
        "get_offers": (f"{prefix}/Offers/", {}),
    }


@pytest.mark.parametrize(
    "route", ["get_actor_offer", "get_offer", "get_offers"]
)
def test_a_received_offer_reads_the_same_with_and_without_an_ingress_row(
    client_datalayer, datalayer, dl_route_key, receive, route
):
    path, params = _routes(f"/actors/{dl_route_key}/datalayer")[route]

    receive(ingress_row=True)
    with_row = client_datalayer.get(path, params=params)
    datalayer.clear_all()
    receive(ingress_row=False)
    record_only = client_datalayer.get(path, params=params)

    assert with_row.status_code == status.HTTP_200_OK, with_row.text
    assert record_only.status_code == status.HTTP_200_OK, record_only.text
    assert with_row.json() == record_only.json()


def test_a_received_offer_is_served_from_its_record(
    client_datalayer, dl_route_key, receive
):
    receive(ingress_row=False)

    body = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/Offers/{OFFER_UUID}"
    ).json()

    assert body["id"] == OFFER_ID
    assert body["actor"] == FINDER
    # The record keeps the report inline; ingress stores it by id only.
    assert body["object"]["id"] == REPORT_ID


def test_get_offers_keys_a_received_offer_by_the_senders_id(
    client_datalayer, dl_route_key, receive
):
    receive(ingress_row=True)

    data = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/Offers/"
    ).json()

    assert list(data) == [OFFER_ID]


def test_get_offers_lists_received_and_authored_offers(
    client_datalayer, datalayer, dl_route_key, dl_actor_id, receive, offer
):
    receive(ingress_row=False)
    datalayer.create(offer)

    data = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/Offers/"
    ).json()

    assert set(data) == {OFFER_ID, offer.id_}


def test_a_received_activity_of_another_type_is_not_an_offer(
    client_datalayer, datalayer, dl_route_key, dl_actor_id
):
    invite = rm_invite_to_case_activity(
        as_Service(id_=dl_actor_id),
        target=as_VulnerabilityCase(
            id_="https://example.org/cases/c-1", stub_summary="s"
        ),
        actor=FINDER,
        id_=OFFER_ID,
    )
    archive_received(datalayer, invite)
    prefix = f"/actors/{dl_route_key}/datalayer"

    assert client_datalayer.get(f"{prefix}/Offers/").json() == {}
    assert (
        client_datalayer.get(f"{prefix}/Offers/{OFFER_UUID}").status_code
        == status.HTTP_404_NOT_FOUND
    )


def test_an_offer_addressed_to_another_actor_is_not_found(
    client_datalayer, datalayer, dl_route_key
):
    archive_received(datalayer, _received_offer("https://x.example/actors/o"))

    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/Offers/{OFFER_UUID}"
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
