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

from vultron.adapters.utils import strip_id_prefix
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.routers import actors as actors_router
from vultron.adapters.driving.fastapi.routers import (
    datalayer as datalayer_router,
)
from vultron.wire.as2.vocab.objects.embargo_policy import as_EmbargoPolicy
from vultron.wire.as2.vocab.objects.vultron_actor import (
    as_VultronApplication,
    as_VultronGroup,
    as_VultronOrganization,
    as_VultronPerson,
    as_VultronService,
)


def _route_key(object_id: str) -> str:
    return strip_id_prefix(object_id)


def _host_actor(actor):
    """Make the node *host* *actor*, then seed its record in its own store.

    ``GET /actors/`` enumerates the actors this node hosts, and under ADR-0070
    that means the actors for which a store exists — for an in-memory URL, the
    in-process store registry.  Creating an actor's record inside some *other*
    actor's store therefore does not make it hosted; opening its own store does.
    Returns the store so callers can close it.
    """
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer

    # get_datalayer(), not a bare SqliteDataLayer(): only the cached factory
    # registers the instance, and for an in-memory URL that registry *is* the
    # list of hosted actors (there are no files to enumerate).
    dl = get_datalayer(actor.id_, db_url="sqlite:///:memory:")
    dl.create(object_to_record(actor))
    return dl


@pytest.fixture
def client_actors(datalayer):
    from fastapi import Path as FastAPIPath
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer
    from vultron.adapters.driving.fastapi.deps import get_actor_dl

    def _in_memory_actor_dl(actor_id: str = FastAPIPath(...)):
        """Per-actor override: the addressed actor's own in-memory store.

        Overriding with a single fixed DataLayer would defeat the routing this
        file exercises — ``get_actor_dl`` resolves the path segment to a
        canonical URI and opens *that* actor's store (ADR-0070), so a one-store
        override makes every actor id resolve to the same rows.  The only thing
        that needs overriding is the backing URL: the configured db_url is a
        file, and tests must stay in memory.
        """
        return get_datalayer(
            canonical_actor_uri(actor_id), db_url="sqlite:///:memory:"
        )

    app = FastAPI()
    app.include_router(actors_router.router)
    app.dependency_overrides[get_actor_dl] = _in_memory_actor_dl
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


@pytest.fixture
def client_datalayer(datalayer):
    from fastapi import Path as FastAPIPath
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer
    from vultron.adapters.driving.fastapi.deps import get_actor_dl

    def _in_memory_actor_dl(actor_id: str = FastAPIPath(...)):
        return get_datalayer(
            canonical_actor_uri(actor_id), db_url="sqlite:///:memory:"
        )

    app = FastAPI()
    app.include_router(datalayer_router.router)
    app.dependency_overrides[get_actor_dl] = _in_memory_actor_dl
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


@pytest.fixture
def embargo_policy():
    from datetime import timedelta

    return as_EmbargoPolicy(
        actor_id="https://example.org/actors/alice",
        inbox="https://example.org/actors/alice/inbox",
        preferred_duration=timedelta(days=90),
    )


# Actor ids must be canonical under the node's own base URL.  ``GET
# /actors/{segment}`` resolves the segment to an actor URI by *computation*
# (base_url + "actors/" + segment, ADR-0070) rather than by scanning a shared
# store for an id ending in that segment, so an id under some other authority
# can never be addressed on this node — it is not an actor this node hosts.
@pytest.fixture
def vultron_person(embargo_policy):
    return as_VultronPerson(
        name="Alice",
        id_=canonical_actor_uri("alice"),
        embargo_policy=embargo_policy,
    )


@pytest.fixture
def vultron_organization(embargo_policy):
    return as_VultronOrganization(
        name="ACME Corp",
        id_=canonical_actor_uri("acme"),
        embargo_policy=embargo_policy,
    )


@pytest.fixture
def vultron_service(embargo_policy):
    return as_VultronService(
        name="VulnBot",
        id_=canonical_actor_uri("vulnbot"),
        embargo_policy=embargo_policy,
    )


@pytest.fixture
def vultron_application(embargo_policy):
    return as_VultronApplication(
        name="VulnApp",
        id_=canonical_actor_uri("vulnapp"),
        embargo_policy=embargo_policy,
    )


@pytest.fixture
def vultron_group(embargo_policy):
    return as_VultronGroup(
        name="VulnGroup",
        id_=canonical_actor_uri("vulngroup"),
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
    _host_actor(actor)

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
    _host_actor(actor)

    resp = client_actors.get(f"/actors/{_route_key(actor.id_)}")
    assert resp.status_code == 200
    data = resp.json()
    assert "embargoPolicy" in data, (
        f"Response for {actor_type} actor missing 'embargoPolicy' field. "
        f"Keys: {list(data.keys())}"
    )


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
def test_get_actor_profile_includes_embargo_policy(
    client_actors, datalayer, request, fixture_name, actor_type
):
    """GET /actors/{actor_id}/profile MUST preserve subtype fields."""
    actor = request.getfixturevalue(fixture_name)
    _host_actor(actor)

    resp = client_actors.get(f"/actors/{_route_key(actor.id_)}/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert "embargoPolicy" in data, (
        f"Response for {actor_type} actor profile missing 'embargoPolicy' field. "
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
    _host_actor(vultron_person)

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

    # The debug router is actor-scoped in its path now (ADR-0070): there is no
    # node-wide store to inspect, so the record goes in this actor's own store
    # and the request names that actor.
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer

    hosted = get_datalayer(vultron_person.id_, db_url="sqlite:///:memory:")
    hosted.create(
        StorableRecord(
            id_=vultron_person.id_,
            type_="Actor",
            data_=vultron_person.model_dump(mode="json"),
        )
    )

    resp = client_datalayer.get(
        f"/actors/{_route_key(vultron_person.id_)}/datalayer/Actors/"
    )
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
