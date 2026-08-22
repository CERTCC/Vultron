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

"""Tests for the /info endpoint (D5-1-G1).

Verifies that GET /info returns the configured VULTRON_SERVER__BASE_URL and the
list of actor IDs registered in the shared DataLayer.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.routers import info as info_router
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Person,
    as_Organization,
)


@pytest.fixture
def client_info():
    """GET /info takes no DataLayer.

    It reports the actors this node *hosts*, enumerated from the per-actor stores
    that exist (ADR-0070), so there is no dependency to override — an actor is
    listed because a store was opened for it, not because a row was written.
    """
    from vultron.adapters.driven.datalayer_sqlite import reset_datalayer

    reset_datalayer()
    app = FastAPI()
    app.include_router(info_router.router)
    client = TestClient(app)
    yield client
    reset_datalayer()


def test_info_returns_200(client_info):
    """D5-1-G1: GET /info MUST return 200."""
    resp = client_info.get("/info")
    assert resp.status_code == 200


def test_info_response_has_base_url(client_info):
    """D5-1-G1: GET /info response MUST include base_url field."""
    resp = client_info.get("/info")
    data = resp.json()
    assert "base_url" in data
    assert isinstance(data["base_url"], str)
    assert len(data["base_url"]) > 0


def test_info_response_has_actors_list(client_info):
    """D5-1-G1: GET /info response MUST include actors list."""
    resp = client_info.get("/info")
    data = resp.json()
    assert "actors" in data
    assert isinstance(data["actors"], list)


def test_info_actors_empty_when_no_actors(client_info):
    """D5-1-G1: actors list is empty when this node hosts no actors."""
    resp = client_info.get("/info")
    data = resp.json()
    assert data["actors"] == []


def test_info_actors_lists_hosted_actors_only(client_info):
    """D5-1-G1: the actors list is the set of actors this node hosts.

    Hosting an actor means holding its store, so each actor here gets its own —
    writing two actor rows into one store would report one host, not two. A peer
    the node merely knows an address for is deliberately absent (ADR-0070
    decision 4): it is not something this node hosts.
    """
    from vultron.adapters.driven.actor_hosts import canonical_actor_uri
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer

    finder_id = canonical_actor_uri("finder")
    vendor_id = canonical_actor_uri("vendorco")
    for actor_id, actor in (
        (finder_id, as_Person(id_=finder_id, name="Finder")),
        (vendor_id, as_Organization(id_=vendor_id, name="VendorCo")),
    ):
        dl = get_datalayer(actor_id, db_url="sqlite:///:memory:")
        dl.create(object_to_record(actor))

    resp = client_info.get("/info")
    assert resp.status_code == 200
    data = resp.json()
    assert finder_id in data["actors"]
    assert vendor_id in data["actors"]
