#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from urllib.parse import quote

from fastapi import status

from vultron.adapters.driven.db_record import object_to_record
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant


def test_get_offers_returns_empty_dict_when_no_offers(
    client_datalayer, dl_route_key
):
    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/Offers/"
    )
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), dict)
    assert len(response.json()) == 0


def test_get_offers_includes_created_offer(
    client_datalayer, datalayer, offer, dl_route_key
):
    datalayer.create(object_to_record(offer))
    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/Offers/"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert offer.id_ in data


def test_get_offer_by_id_returns_offer_fields(
    client_datalayer, datalayer, offer, dl_route_key
):
    datalayer.create(object_to_record(offer))
    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/Offer/",
        params={"object_id": offer.id_},
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["id"] == offer.id_
    # actor key name comes from the router's encoding
    assert body.get("actor") == offer.actor


def test_get_vulnerability_reports_returns_empty_dict_when_no_reports(
    client_datalayer, dl_route_key
):
    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/VulnerabilityReports/"
    )
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), dict)
    assert len(response.json()) == 0


def test_get_vulnerability_reports_includes_created_report(
    client_datalayer, datalayer, report, dl_route_key
):
    datalayer.create(report)
    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/VulnerabilityReports/"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert report.id_ in data


def test_reports_shortcut_endpoint_returns_same_results(
    client_datalayer, datalayer, report, dl_route_key
):
    datalayer.create(report)
    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/Reports/"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert report.id_ in data


def test_get_report_by_id_returns_report(
    client_datalayer, datalayer, report, dl_route_key
):
    datalayer.create(report)
    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/Report/", params={"id": report.id_}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == report.id_


def test_reset_endpoint_clears_all_data(
    client_datalayer, datalayer, report, offer, dl_route_key
):
    datalayer.create(object_to_record(offer))
    datalayer.create(report)

    # sanity: ensure they exist before reset
    assert datalayer.by_type("Offer") is not None
    assert datalayer.by_type("VulnerabilityReport") is not None

    resp = client_datalayer.delete("/admin/datalayer/reset/")
    assert resp.status_code == status.HTTP_200_OK

    resp_offers = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/Offers/"
    )
    assert resp_offers.status_code == status.HTTP_200_OK
    assert len(resp_offers.json()) == 0

    resp_reports = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/Reports/"
    )
    assert resp_reports.status_code == status.HTTP_200_OK
    assert len(resp_reports.json()) == 0


# ---------------------------------------------------------------------------
# Regression tests for #610: URL-format (HTTP URL) keys must be fetchable
# ---------------------------------------------------------------------------

_HTTP_PARTICIPANT_ID = (
    "http://vendor:7999/api/v2/actors/case-actor-abc/participant"
)


def test_get_by_http_url_key_returns_stored_record(
    client_datalayer, datalayer, dl_route_key
):
    """GET /datalayer/{url-encoded-http-id} must return the stored record.

    Regression: Starlette decodes %2F to / before routing, so single-segment
    /{key} never matched URL-format IDs.  Fix: use /{key:path} as catch-all.
    """
    participant = as_CaseParticipant(id_=_HTTP_PARTICIPANT_ID)
    datalayer.create(object_to_record(participant))

    encoded = quote(_HTTP_PARTICIPANT_ID, safe="")
    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/{encoded}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == _HTTP_PARTICIPANT_ID


def test_get_by_http_url_key_not_found_returns_404(
    client_datalayer, dl_route_key
):
    """Non-existent HTTP URL key returns 404 (not a routing error)."""
    encoded = quote(
        "http://vendor:7999/api/v2/actors/missing/participant", safe=""
    )
    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/{encoded}"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_specific_routes_not_shadowed_by_catch_all(
    client_datalayer, datalayer, offer, dl_route_key
):
    """Specific routes (e.g. /Offers/) still resolve correctly after fix."""
    datalayer.create(object_to_record(offer))
    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/Offers/"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert offer.id_ in data


# ---------------------------------------------------------------------------
# Regression tests for #1515: GET /Actors/{actor_id}/outbox/ must return
# the actor's actual queued outbox items, not an empty collection.
# ---------------------------------------------------------------------------


def test_get_actor_outbox_returns_404_for_unknown_actor(
    client_datalayer, dl_route_key
):
    """Non-existent actor returns 404."""
    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/Actors/no-such-actor/outbox/"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_actor_outbox_returns_empty_items_when_queue_is_empty(
    client_datalayer, datalayer, dl_actor_id, dl_route_key
):
    """Existing actor with no queued outbox items returns an empty items list.

    An outbox is addressed as the path actor's *own* — there is no
    ``Actors/{other}/outbox/`` form, because a store holds exactly one actor's
    queue (ADR-0072). So the actor under test is the store's own actor.
    """
    from vultron.adapters.driven.db_record import object_to_record
    from vultron.wire.as2.vocab.base.objects.actors import as_Service

    actor = as_Service(id_=dl_actor_id, name="test-empty-outbox")
    datalayer.create(object_to_record(actor))

    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/outbox/"
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body.get("type") == "OrderedCollection"
    assert body.get("orderedItems", body.get("items", None)) == []


def test_get_actor_outbox_returns_queued_activity_ids(
    client_datalayer, datalayer, offer, dl_actor_id, dl_route_key
):
    """After enqueuing an activity for an actor, the endpoint must return it.

    Regression for #1515: ADR-0034 changed dl.read() to return CoreActor
    (outbox=str URI), so the old as_Actor.model_validate() path produced
    an empty as_OrderedCollection with no items.
    """
    from vultron.adapters.driven.db_record import object_to_record
    from vultron.wire.as2.vocab.base.objects.actors import as_Service

    actor = as_Service(id_=dl_actor_id, name="test-nonempty-outbox")
    datalayer.create(object_to_record(actor))

    # Persist the activity and record it in the actor's outbox queue.
    datalayer.create(object_to_record(offer))
    datalayer.outbox_append(offer.id_)

    response = client_datalayer.get(
        f"/actors/{dl_route_key}/datalayer/outbox/"
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body.get("type") == "OrderedCollection"
    items = body.get("orderedItems", body.get("items", []))
    assert len(items) == 1
    item = items[0]
    # Rehydrated item should have the activity's id
    assert item.get("id") == offer.id_
