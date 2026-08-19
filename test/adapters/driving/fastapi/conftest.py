#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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

"""
Provides pytest fixtures for testing the FastAPI v2 application.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.app import app_v2 as app
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driving.fastapi.inbox_pipeline import (
    InboxPipeline,
    build_test_pipeline,
)


@pytest.fixture
def client(datalayer):
    from vultron.adapters.driven.datalayer import get_datalayer

    app.dependency_overrides = {}
    app.dependency_overrides[get_datalayer] = lambda: datalayer
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


@pytest.fixture
def dl_route_key():
    """The URL path segment addressing this test's actor."""
    return "test-actor"


@pytest.fixture
def dl_actor_id(dl_route_key):
    """The actor whose store the ``datalayer`` fixture is.

    An actor is a process with API endpoints and its id *is* the URL that reaches
    it, so a hosted actor is named ``{base_url}/actors/{slug}`` with its inbox at
    ``{id}/inbox``. Deriving the id from the slug keeps the two in step; an id
    under some other authority names a process elsewhere and cannot be addressed
    here at all.
    """
    return canonical_actor_uri(dl_route_key)


@pytest.fixture
def datalayer(dl_actor_id):
    from vultron.adapters.driven.datalayer import (
        get_datalayer,
        reset_datalayer,
    )

    # Reset the singleton to avoid stale instances
    reset_datalayer()
    # Use in-memory storage for tests.  get_datalayer(), not a bare
    # SqliteDataLayer(): only the cached factory registers the instance, and for
    # an in-memory URL that registry is what makes the node a *host* of this
    # actor, which GET /actors/ and the outbox monitor enumerate.
    datalayer = get_datalayer(dl_actor_id, db_url="sqlite:///:memory:")
    # Clear the datalayer before each test
    datalayer.clear_all()
    yield datalayer
    # Clear the datalayer after each test
    datalayer.clear_all()
    # Reset singleton for next test
    reset_datalayer()


@pytest.fixture
def hosted_actor(datalayer, dl_actor_id):
    """Seed the addressed actor's own record into its own store.

    Every route under ``/actors/{actor_id}/`` resolves the actor before serving
    anything and answers ``404 Actor not found`` otherwise, so a test addressing
    one needs its record to exist.  An actor's own record living in its own store
    is the Actor Knowledge Model, so this is setup those routes are entitled to
    expect.

    Opt-in rather than part of ``datalayer``: some tests in this package assert
    on an *empty* store, and seeding unconditionally would change what they see.
    """
    from vultron.wire.as2.vocab.base.objects.actors import as_Service

    actor = as_Service(id_=dl_actor_id, name="Hosted Test Actor")
    datalayer.create(actor)
    return actor


@pytest.fixture
def test_pipeline() -> (
    Generator[tuple[InboxPipeline, SqliteDataLayer], None, None]
):
    dl = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )
    try:
        yield build_test_pipeline(dl), dl
    finally:
        dl.close()
