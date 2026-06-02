#!/usr/bin/env python
"""
Regression tests for actor API serialization completeness.

Verifies that GET /actors/ and POST /actors/ return all fields from the
concrete actor subtype, not only fields declared on the base ``as_Actor``
class (HTTP-08-001).
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

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.routers import actors as actors_router
from vultron.adapters.driving.fastapi.routers import (
    datalayer as datalayer_router,
)
from vultron.wire.as2.vocab.objects.embargo_policy import EmbargoPolicy
from vultron.wire.as2.vocab.objects.vultron_actor import (
    VultronApplication,
    VultronGroup,
    VultronOrganization,
    VultronPerson,
    VultronService,
)


@pytest.fixture
def client_actors(datalayer):
    from vultron.adapters.driven.datalayer import get_shared_dl

    app = FastAPI()
    app.include_router(actors_router.router)
    app.dependency_overrides[get_shared_dl] = lambda: datalayer
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


@pytest.fixture
def client_datalayer(datalayer):
    from vultron.adapters.driven.datalayer import get_shared_dl

    app = FastAPI()
    app.include_router(datalayer_router.router)
    app.dependency_overrides[get_shared_dl] = lambda: datalayer
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


@pytest.fixture
def embargo_policy():
    from datetime import timedelta

    return EmbargoPolicy(
        actor_id="https://example.org/actors/alice",
        inbox="https://example.org/actors/alice/inbox",
        preferred_duration=timedelta(days=90),
    )


@pytest.fixture
def vultron_person(embargo_policy):
    return VultronPerson(
        name="Alice",
        id_="https://example.org/actors/alice",
        embargo_policy=embargo_policy,
    )


@pytest.fixture
def vultron_organization(embargo_policy):
    return VultronOrganization(
        name="ACME Corp",
        id_="https://example.org/actors/acme",
        embargo_policy=embargo_policy,
    )


@pytest.fixture
def vultron_service(embargo_policy):
    return VultronService(
        name="VulnBot",
        id_="https://example.org/actors/vulnbot",
        embargo_policy=embargo_policy,
    )


@pytest.fixture
def vultron_application(embargo_policy):
    return VultronApplication(
        name="VulnApp",
        id_="https://example.org/actors/vulnapp",
        embargo_policy=embargo_policy,
    )


@pytest.fixture
def vultron_group(embargo_policy):
    return VultronGroup(
        name="VulnGroup",
        id_="https://example.org/actors/vulngroup",
        embargo_policy=embargo_policy,
    )


# ---------------------------------------------------------------------------
# GET /actors/ serialization tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name,actor_type",
    [
        ("vultron_person", "Person"),
        ("vultron_organization", "Organization"),
        ("vultron_service", "Service"),
        ("vultron_application", "Application"),
        ("vultron_group", "Group"),
    ],
)
def test_get_actors_list_includes_embargo_policy(
    client_actors, datalayer, request, fixture_name, actor_type
):
    """GET /actors/ MUST include embargo_policy for Vultron actor subtypes.

    Regression test for HTTP-08-001 violation where response_model=list[as_Actor]
    silently dropped subclass-specific fields.
    """
    actor = request.getfixturevalue(fixture_name)
    datalayer.create(object_to_record(actor))

    resp = client_actors.get("/actors/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)

    matching = [
        item
        for item in data
        if item.get("id") == actor.id_
        or item.get("id", "").endswith(actor.id_)
    ]
    assert (
        matching
    ), f"Actor {actor.id_} not found in response. IDs: {[d.get('id') for d in data]}"
    actor_data = matching[0]
    assert "embargoPolicy" in actor_data, (
        f"Response for {actor_type} actor missing 'embargoPolicy' field. "
        f"Keys: {list(actor_data.keys())}"
    )


# ---------------------------------------------------------------------------
# GET /actors/{actor_id} serialization tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name,actor_type",
    [
        ("vultron_person", "Person"),
        ("vultron_organization", "Organization"),
        ("vultron_service", "Service"),
        ("vultron_application", "Application"),
        ("vultron_group", "Group"),
    ],
)
def test_get_actor_by_id_includes_embargo_policy(
    client_actors, datalayer, request, fixture_name, actor_type
):
    """GET /actors/{actor_id} MUST include embargo_policy for Vultron actor subtypes.

    Regression test for HTTP-08-001 violation where response_model=as_Actor +
    as_Actor.model_validate() double-dropped subclass-specific fields.
    """
    actor = request.getfixturevalue(fixture_name)
    datalayer.create(object_to_record(actor))

    resp = client_actors.get(f"/actors/{actor.id_}")
    assert resp.status_code == 200
    data = resp.json()
    assert "embargoPolicy" in data, (
        f"Response for {actor_type} actor missing 'embargoPolicy' field. "
        f"Keys: {list(data.keys())}"
    )


# ---------------------------------------------------------------------------
# POST /actors/ serialization tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "actor_type",
    ["Person", "Organization", "Service", "Application", "Group"],
)
def test_post_actors_create_returns_actor_type(client_actors, actor_type):
    """POST /actors/ MUST return the concrete actor type field.

    Regression test for HTTP-08-001 violation where -> as_Actor return
    annotation stripped subclass fields from the created actor response.
    """
    resp = client_actors.post(
        "/actors/",
        json={"name": f"Test {actor_type}", "actor_type": actor_type},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert (
        data.get("type") == actor_type
    ), f"Expected type={actor_type!r}, got {data.get('type')!r}"


def test_post_actors_idempotency_returns_full_actor(
    client_actors, datalayer, vultron_person
):
    """POST /actors/ idempotency path MUST return all subclass fields.

    Regression test for HTTP-08-001 violation where the idempotency branch used
    as_Actor.model_validate(), dropping subclass-specific fields like embargo_policy.
    """
    datalayer.create(object_to_record(vultron_person))

    resp = client_actors.post(
        "/actors/",
        json={
            "name": vultron_person.name,
            "actor_type": "Person",
            "id": vultron_person.id_,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert (
        "embargoPolicy" in data
    ), f"Idempotency response missing 'embargoPolicy'. Keys: {list(data.keys())}"


# ---------------------------------------------------------------------------
# GET /datalayer/Actors/ serialization tests
# ---------------------------------------------------------------------------


def test_datalayer_get_actors_includes_embargo_policy(
    client_datalayer, datalayer, vultron_person
):
    """GET /datalayer/Actors/ MUST include embargo_policy for Vultron actor subtypes.

    Regression test for HTTP-08-001 violation where -> dict[str, as_Actor]
    return annotation stripped subclass fields.
    """
    from vultron.core.ports.datalayer import StorableRecord

    # /datalayer/Actors/ currently queries the "Actor" table specifically.
    # Store a record in that table whose payload is a concrete Person actor.
    datalayer.create(
        StorableRecord(
            id_=vultron_person.id_,
            type_="Actor",
            data_=vultron_person.model_dump(mode="json"),
        )
    )

    resp = client_datalayer.get("/datalayer/Actors/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)

    matching = {
        k: v
        for k, v in data.items()
        if v.get("id") == vultron_person.id_
        or v.get("id", "").endswith(vultron_person.id_)
    }
    assert matching, (
        f"Person actor not found in /datalayer/Actors/ response. "
        f"IDs: {[v.get('id') for v in data.values()]}"
    )
    person_data = next(iter(matching.values()))
    assert (
        "embargoPolicy" in person_data
    ), f"Response missing 'embargoPolicy'. Keys: {list(person_data.keys())}"
