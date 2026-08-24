#!/usr/bin/env python

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
"""The actor-scoped datalayer routes must not be shadowed by `{actor_id:path}`.

ADR-0072 deleted the unscoped ``/datalayer/…`` view and moved the debug and
inspection endpoints under ``/actors/{actor_id}/datalayer/…``.  That put them
behind the actors router's ``GET /actors/{actor_id:path}``, whose ``:path``
converter matches slashes.  Starlette matches routes in registration order, so
with the actors router registered first, ``/actors/vendor/datalayer/urn:uuid:x``
matched the actors route with ``actor_id = "vendor/datalayer/urn:uuid:x"`` and
answered ``404 Actor not found``.

Every route in the datalayer router was unreachable, and the symptom was
indistinguishable from a missing actor — no 500, no routing error, just a
plausible 404.  It also would have broken Phase 4b of #2238, where the demo's
``DataLayerClient.dl_path()`` reads target exactly these paths.

These tests assert reachability by *which endpoint answered*, not merely by
status code, since the bug produced a 404 that a working route also produces.

Issue: #2238
"""

import pytest
from fastapi.testclient import TestClient

from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import (
    get_datalayer,
    reset_datalayer,
)
from vultron.adapters.driving.fastapi.main import app
from vultron.wire.as2.vocab.base.objects.actors import as_Service

ACTOR_SEGMENT = "route-reachable-actor"
ACTOR_ID = canonical_actor_uri(ACTOR_SEGMENT)


@pytest.fixture
def hosted_actor_store():
    """An in-memory store for an actor addressable by short path segment."""
    reset_datalayer(ACTOR_ID)
    dl = get_datalayer(ACTOR_ID, db_url="sqlite:///:memory:")
    dl.clear_all()
    dl.create(as_Service(id_=ACTOR_ID, name="Route Reachable Actor"))
    yield dl
    dl.clear_all()
    reset_datalayer(ACTOR_ID)


@pytest.fixture
def client(hosted_actor_store):
    with TestClient(app) as c:
        yield c


# Which endpoint answered is readable from the 404 body, and that is the
# discriminator these tests use.  The shadowing actors route answers
# ``{"detail": "Actor not found."}`` because it read the whole tail of the path
# as an actor id; the datalayer route raises a bare 404, so FastAPI's default
# ``{"detail": "Not Found"}``.  Matching route templates directly is not an
# option here: the routers are included lazily, so `app_v2.routes` holds wrapper
# objects rather than the `APIRoute`s that ultimately match.
_SHADOWED_DETAIL = "Actor not found."


def test_datalayer_key_route_is_not_shadowed_by_actor_path_route(client):
    """A datalayer read for a missing key 404s *as the datalayer route*.

    The actor exists, so ``Actor not found.`` can only mean the request was
    swallowed by ``GET /actors/{actor_id:path}`` with the rest of the path
    misread as the actor id.
    """
    resp = client.get(
        f"/api/v2/actors/{ACTOR_SEGMENT}/datalayer/urn:uuid:definitely-absent"
    )
    assert resp.status_code == 404
    assert resp.json().get("detail") != _SHADOWED_DETAIL, (
        "the actor-scoped datalayer read was shadowed by"
        " GET /actors/{actor_id:path} — the actor exists, so this 404 is a"
        " routing failure, not a missing object"
    )


def test_datalayer_contents_route_is_not_shadowed(client, hosted_actor_store):
    """The whole-store read is reachable too, not just the keyed read."""
    resp = client.get(f"/api/v2/actors/{ACTOR_SEGMENT}/datalayer/")
    assert resp.status_code == 200, resp.text


def test_actor_profile_route_still_reachable(client, hosted_actor_store):
    """Reordering must not shadow the actors router in the other direction.

    ``/profile`` has no ``/datalayer/`` segment, so the narrower datalayer
    prefix must not match it.  A 404 here would mean the reorder broke the
    actors router.
    """
    resp = client.get(f"/api/v2/actors/{ACTOR_SEGMENT}/profile")
    assert resp.status_code == 200, resp.text


def test_datalayer_read_answers_from_the_addressed_actors_store(
    client, hosted_actor_store
):
    """End-to-end: the reachable route serves the addressed actor's own rows.

    Guards the reachability fix against a regression that keeps the route
    matchable but resolves the segment to a different store — the failure this
    whole issue is about.
    """
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(name="R", content="body")
    hosted_actor_store.create(report)

    resp = client.get(f"/api/v2/actors/{ACTOR_SEGMENT}/datalayer/{report.id_}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["content"] == "body"

    # A different actor's segment must not see it.
    other_segment = "some-other-actor"
    reset_datalayer(canonical_actor_uri(other_segment))
    other = get_datalayer(
        canonical_actor_uri(other_segment), db_url="sqlite:///:memory:"
    )
    other.clear_all()
    other.create(
        as_Service(id_=canonical_actor_uri(other_segment), name="Other")
    )
    try:
        resp = client.get(
            f"/api/v2/actors/{other_segment}/datalayer/{report.id_}"
        )
        assert resp.status_code == 404, resp.text
    finally:
        other.clear_all()
        reset_datalayer(canonical_actor_uri(other_segment))
