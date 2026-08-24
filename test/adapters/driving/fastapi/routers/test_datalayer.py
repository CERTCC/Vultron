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


# ---------------------------------------------------------------------------
# The admin reset is a *node*-level operation: it must clear every hosted store.
# ---------------------------------------------------------------------------


class TestResetFansOutOverEveryHostedActor:
    """Under ADR-0072 there is no single store to clear.

    The demo harness and the autouse isolation fixture both depend on this
    endpoint actually emptying the node. Clearing one actor and reporting success
    is the failure mode that matters: the next scenario then starts with another
    actor's rows still present, and the resulting cross-talk looks like a protocol
    bug rather than a dirty fixture.
    """

    @staticmethod
    def _app_with(actor_dls):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from vultron.adapters.driving.fastapi.deps import get_hosted_actor_dls
        from vultron.adapters.driving.fastapi.routers import (
            datalayer as datalayer_router,
        )

        app = FastAPI()
        app.include_router(datalayer_router.admin_router)
        app.dependency_overrides[get_hosted_actor_dls] = lambda: actor_dls
        return TestClient(app)

    @staticmethod
    def _store(slug):
        from vultron.adapters.driven.actor_hosts import canonical_actor_uri
        from vultron.adapters.driven.datalayer_sqlite import get_datalayer

        actor_id = canonical_actor_uri(slug)
        dl = get_datalayer(actor_id, db_url="sqlite:///:memory:")
        dl.clear_all()
        return actor_id, dl

    def test_clears_every_actors_store_not_just_the_first(self, offer, report):
        vendor_id, vendor_dl = self._store("reset-vendor")
        finder_id, finder_dl = self._store("reset-finder")
        vendor_dl.create(object_to_record(offer))
        finder_dl.create(report)
        assert any(vendor_dl.count_all().values())
        assert any(finder_dl.count_all().values())

        client = self._app_with({vendor_id: vendor_dl, finder_id: finder_dl})
        resp = client.delete("/admin/datalayer/reset/")

        assert resp.status_code == status.HTTP_200_OK
        # ``count_all`` keeps its keys and zeroes them, so "empty" is all-zero
        # rather than ``{}``.
        assert not any(
            vendor_dl.count_all().values()
        ), "vendor's store was not cleared"
        assert not any(
            finder_dl.count_all().values()
        ), "finder's store was not cleared"

    def test_reports_one_entry_per_actor(self, offer):
        vendor_id, vendor_dl = self._store("reset-count-vendor")
        finder_id, finder_dl = self._store("reset-count-finder")
        vendor_dl.create(object_to_record(offer))

        body = (
            self._app_with({vendor_id: vendor_dl, finder_id: finder_dl})
            .delete("/admin/datalayer/reset/")
            .json()
        )

        assert body["actors"] == 2
        assert set(body["n_items"]) == {vendor_id, finder_id}

    def test_a_node_hosting_nothing_resets_successfully(self):
        """A clean node is not an error — the demo harness resets before seeding."""
        resp = self._app_with({}).delete("/admin/datalayer/reset/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["actors"] == 0

    def test_it_honours_the_apps_own_stores(self, offer):
        """The reason the set arrives via a dependency rather than a loop.

        An app whose stores came from ``_auto_inject_isolated_datalayer`` keeps
        them in ``app.state.actor_dls``. A loop over the process-global
        ``get_datalayer`` would clear the *on-disk* stores, report success, and
        leave the app's real stores untouched — a reset that resets nothing while
        returning 200.
        """
        registered_id, registered_dl = self._store("reset-registered")
        untouched_id, untouched_dl = self._store("reset-untouched")
        registered_dl.create(object_to_record(offer))
        untouched_dl.create(object_to_record(offer))

        client = self._app_with({registered_id: registered_dl})
        body = client.delete("/admin/datalayer/reset/").json()

        assert not any(registered_dl.count_all().values())
        assert any(
            untouched_dl.count_all().values()
        ), "only the stores the app declared may be cleared"
        assert list(body["n_items"]) == [registered_id]

    def test_it_is_not_mounted_on_the_actor_scoped_router(self):
        """Kept off ``/actors/{id}/`` so it cannot read as one actor reaching
        into another's data — the shape ADR-0072 exists to prevent."""
        from vultron.adapters.driving.fastapi.routers import (
            datalayer as datalayer_router,
        )

        # ``path`` is on the concrete route classes, not on ``BaseRoute``.
        # Probed rather than narrowed so that a mount or websocket route named
        # "reset" still trips the negative assertion below.
        def _paths(routes) -> list[str]:
            return [str(getattr(r, "path", "")) for r in routes]

        assert not any(
            "reset" in p for p in _paths(datalayer_router.router.routes)
        )
        assert any(
            "reset" in p for p in _paths(datalayer_router.admin_router.routes)
        )
