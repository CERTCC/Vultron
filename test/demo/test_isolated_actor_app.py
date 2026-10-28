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
"""Tests for the ``create_isolated_actor_app`` multi-node harness (#5338).

An in-memory store exists while it is open, and an open store is what makes a
node list an actor as hosted (DL-07-011).  So building a node must open no
store: a node hosts an actor only once the actor is created there, or a test
reads the node's ``dl``.
"""

import pytest

from test.demo.conftest import _TestClientRouter, create_isolated_actor_app
from vultron.adapters.driven.datalayer_sqlite.engine import (
    open_memory_store_slugs,
)

_BASE = "http://harness-node.test"


@pytest.mark.spec("DL-07-013")
def test_building_a_node_opens_no_store():
    """No ``primary`` actor is hosted on a node that never created one."""
    iso = create_isolated_actor_app(_BASE, _TestClientRouter())

    with iso.client as client:
        assert client.get("/api/v2/actors/").json() == []
        assert client.get("/api/v2/info").json()["actors"] == []
        assert (
            client.delete("/api/v2/admin/datalayer/reset/").json()["n_items"]
            == {}
        )

    assert open_memory_store_slugs(iso.db_url) == set()


def test_dl_opens_the_nodes_own_actor_store_on_first_use():
    """Reading ``dl`` opens that store, the same instance the routes get."""
    iso = create_isolated_actor_app(
        _BASE, _TestClientRouter(), actor_slug="vendor"
    )

    store = iso.dl

    assert store is iso.store_for(iso.actor_id)
    assert iso.actor_id == f"{_BASE}/api/v2/actors/vendor"
    assert open_memory_store_slugs(iso.db_url) == {"vendor"}
    with iso.client as client:
        assert client.get("/api/v2/info").json()["actors"] == [iso.actor_id]


def test_close_disposes_every_store_the_node_opened():
    """``close`` stops the node's whole deployment, not one store."""
    iso = create_isolated_actor_app(
        _BASE, _TestClientRouter(), actor_slug="vendor"
    )
    with iso.client as client:
        resp = client.post(
            "/api/v2/actors/", json={"name": "Case Actor", "id": "case-actor"}
        )
        assert resp.status_code == 201
    assert iso.dl is not None
    assert open_memory_store_slugs(iso.db_url) == {"vendor", "case-actor"}

    iso.close()

    assert open_memory_store_slugs(iso.db_url) == set()
