"""Tests for per-app singleton isolation in create_app() (issue #534).

Verifies that each create_app() call produces an independent application
with its own DataLayer and dispatcher — no shared module-level state.
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute
#    to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype
#  is licensed under a MIT (SEI)-style license, please see LICENSE.md
#  distributed with this Software or contact permission@sei.cmu.edu for full
#  terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import pytest
from fastapi.testclient import TestClient

from vultron.adapters.driving.fastapi import inbox_handler as ih
from vultron.adapters.driving.fastapi.app import create_app


@pytest.fixture
def app1():
    return create_app(docs_url=None, openapi_url=None)


@pytest.fixture
def app2():
    return create_app(docs_url=None, openapi_url=None)


def test_create_app_auto_injects_datalayer(app1):
    """create_app() lifespan should auto-inject a DataLayer override."""
    from vultron.adapters.driving.fastapi.deps import get_actor_dl

    with TestClient(app1):
        assert get_actor_dl in app1.dependency_overrides


def test_create_app_datalayers_are_distinct(app1, app2):
    """Two create_app() instances must not share the same DataLayer."""
    from vultron.adapters.driving.fastapi.deps import get_actor_dl

    with TestClient(app1), TestClient(app2):
        dl1 = app1.dependency_overrides[get_actor_dl]("shared-actor")
        dl2 = app2.dependency_overrides[get_actor_dl]("shared-actor")
        assert dl1 is not dl2


def test_create_app_datalayers_are_isolated(app1, app2):
    """An actor created via app1 must not be visible to app2."""
    from vultron.wire.as2.vocab.base.objects.actors import as_Service

    actor_id = "https://example.org/actors/isolated-test-actor"
    actor = as_Service(id_=actor_id, name="IsolatedTestActor")

    with TestClient(app1), TestClient(app2):
        from vultron.adapters.driving.fastapi.deps import get_actor_dl

        dl1 = app1.dependency_overrides[get_actor_dl]("shared-actor")
        dl2 = app2.dependency_overrides[get_actor_dl]("shared-actor")

        dl1.save(actor)

        assert dl1.read(actor_id) is not None
        assert dl2.read(actor_id) is None


def test_create_app_datalayer_override_not_clobbered(app1):
    """A pre-registered dependency_overrides entry is not overwritten."""
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
    from vultron.adapters.driving.fastapi.deps import get_actor_dl

    custom_dl = SqliteDataLayer(
        db_url="sqlite:///:memory:", actor_id="custom-actor"
    )
    # Signature mirrors the real dependency, which takes the path's actor id.
    app1.dependency_overrides[get_actor_dl] = lambda actor_id=None: custom_dl

    with TestClient(app1):
        resolved = app1.dependency_overrides[get_actor_dl]("shared-actor")
        assert resolved is custom_dl


def test_create_app_per_app_dispatcher_on_state(app1):
    """create_app() lifespan stores a dispatcher on app.state.dispatcher."""
    with TestClient(app1):
        d = getattr(app1.state, "dispatcher", None)
        assert d is not None
        assert hasattr(d, "dispatch") and callable(d.dispatch)


def test_create_app_does_not_mutate_global_dispatcher(app1):
    """create_app() lifespan must not overwrite the module-level _DISPATCHER_SLOT."""
    original = ih._DISPATCHER_SLOT.value

    with TestClient(app1):
        assert ih._DISPATCHER_SLOT.value is original


def test_create_app_dispatchers_are_distinct(app1, app2):
    """Two create_app() instances must each have their own dispatcher."""
    with TestClient(app1), TestClient(app2):
        d1 = app1.state.dispatcher
        d2 = app2.state.dispatcher
        assert d1 is not None
        assert d2 is not None
        assert d1 is not d2


def test_create_app_lifespan_cleanup(app1):
    """After TestClient exits the lifespan, per-app state is cleared."""
    from vultron.adapters.driving.fastapi.deps import get_actor_dl

    with TestClient(app1):
        pass

    assert not hasattr(app1.state, "emitter")
    assert app1.state.dispatcher is None
    assert getattr(app1.state, "shared_dl", None) is None
    assert get_actor_dl not in app1.dependency_overrides


# ---------------------------------------------------------------------------
# Two nodes in one process: each enumerates only its own deployment
# (DL-07-011 to DL-07-014, #5338).
# ---------------------------------------------------------------------------

_NODE_A = "http://node-a.test/api/v2"
_NODE_B = "http://node-b.test/api/v2"


def _create_actor(client: TestClient, slug: str) -> str:
    resp = client.post(
        "/api/v2/actors/", json={"name": slug.title(), "id": slug}
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _store_count(app, actor_id: str) -> int:
    """How many rows *actor_id*'s store holds in *app*'s own deployment."""
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer

    store = get_datalayer(actor_id, db_url=app.state.db_url)
    return sum(store.count_all().values())


@pytest.fixture
def two_nodes():
    """Two ``create_app`` nodes in one process, each with its own base URL.

    Both host a ``case-actor``: the slug alone does not separate the nodes,
    so a listing that is not read from the node's own deployment shows up
    as a foreign id or a duplicate.
    """
    app_a = create_app(docs_url=None, openapi_url=None, node_base_url=_NODE_A)
    app_b = create_app(docs_url=None, openapi_url=None, node_base_url=_NODE_B)
    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        ids_a = sorted(
            _create_actor(client_a, slug) for slug in ("vendor", "case-actor")
        )
        ids_b = sorted(
            _create_actor(client_b, slug) for slug in ("finder", "case-actor")
        )
        yield app_a, client_a, ids_a, app_b, client_b, ids_b


def test_each_node_lists_only_its_own_actors(two_nodes, caplog):
    """``GET /actors/`` reads the serving node's deployment (DL-07-007).

    The listing alone would not show the defect: a foreign actor's store
    opened in this node's deployment is empty, so it holds no actor record
    to list.  What shows it is the store itself, so the test also checks
    that listing opened no store for a foreign actor (DL-07-013).
    """
    from vultron.adapters.driven.datalayer_sqlite.engine import (
        open_memory_store_slugs,
    )

    app_a, client_a, ids_a, app_b, client_b, ids_b = two_nodes
    caplog.set_level("WARNING")

    listed_a = sorted(a["id"] for a in client_a.get("/api/v2/actors/").json())
    listed_b = sorted(a["id"] for a in client_b.get("/api/v2/actors/").json())

    assert listed_a == ids_a
    assert listed_b == ids_b
    assert open_memory_store_slugs(app_a.state.db_url) == {
        "vendor",
        "case-actor",
    }
    assert open_memory_store_slugs(app_b.state.db_url) == {
        "finder",
        "case-actor",
    }
    assert "shared by two distinct actor ids" not in caplog.text


def test_each_nodes_info_reports_itself(two_nodes):
    """``/info`` names the node's own base URL and actors (DL-07-012)."""
    _app_a, client_a, ids_a, _app_b, client_b, ids_b = two_nodes

    info_a = client_a.get("/api/v2/info").json()
    info_b = client_b.get("/api/v2/info").json()

    assert info_a == {"base_url": _NODE_A, "actors": ids_a}
    assert info_b == {"base_url": _NODE_B, "actors": ids_b}


def test_reset_clears_only_the_serving_nodes_stores(two_nodes):
    """The reset opens each store under the deployment it listed (DL-07-014).

    One of node A's actors is addressed through a path-scoped route first, so
    node A's per-app registry holds it and not the other: the reset must clear
    both, and must leave node B's same-slug ``case-actor`` untouched.
    """
    app_a, client_a, ids_a, app_b, _client_b, ids_b = two_nodes
    vendor_a = next(i for i in ids_a if i.endswith("/vendor"))
    assert client_a.get("/api/v2/actors/vendor").status_code == 200
    assert all(_store_count(app_a, i) for i in ids_a)
    counts_b = {i: _store_count(app_b, i) for i in ids_b}
    assert all(counts_b.values())

    resp = client_a.delete("/api/v2/admin/datalayer/reset/")

    assert resp.status_code == 200
    assert sorted(resp.json()["n_items"]) == ids_a
    assert vendor_a in resp.json()["n_items"]
    assert [_store_count(app_a, i) for i in ids_a] == [0, 0]
    assert {i: _store_count(app_b, i) for i in ids_b} == counts_b
