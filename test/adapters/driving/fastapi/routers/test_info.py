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

Verifies that GET /info returns the configured VULTRON_BASE_URL and the
list of actor IDs registered in the shared DataLayer.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driving.fastapi.routers import info as info_router
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Person,
    as_Organization,
)


@pytest.fixture
def client_info(datalayer):
    app = FastAPI()
    app.include_router(info_router.router)
    app.dependency_overrides[get_datalayer] = lambda: datalayer
    app.dependency_overrides[info_router.get_shared_dl] = lambda: datalayer
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


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
    """D5-1-G1: actors list is empty when no actors are registered."""
    resp = client_info.get("/info")
    data = resp.json()
    assert data["actors"] == []


def test_info_actors_includes_seeded_actors(datalayer):
    """D5-1-G1: actors list reflects actors registered in the DataLayer."""
    person = as_Person(name="Finder")
    org = as_Organization(name="VendorCo")
    datalayer.create(object_to_record(person))
    datalayer.create(object_to_record(org))

    app = FastAPI()
    app.include_router(info_router.router)
    app.dependency_overrides[get_datalayer] = lambda: datalayer
    app.dependency_overrides[info_router.get_shared_dl] = lambda: datalayer
    client = TestClient(app)

    resp = client.get("/info")
    assert resp.status_code == 200
    data = resp.json()
    assert person.id_ in data["actors"]
    assert org.id_ in data["actors"]
    app.dependency_overrides = {}
