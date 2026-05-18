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
    from vultron.adapters.driven.datalayer import get_shared_dl

    with TestClient(app1):
        assert get_shared_dl in app1.dependency_overrides


def test_create_app_datalayers_are_distinct(app1, app2):
    """Two create_app() instances must not share the same DataLayer."""
    from vultron.adapters.driven.datalayer import get_shared_dl

    with TestClient(app1), TestClient(app2):
        dl1 = app1.dependency_overrides[get_shared_dl]()
        dl2 = app2.dependency_overrides[get_shared_dl]()
        assert dl1 is not dl2


def test_create_app_datalayers_are_isolated(app1, app2):
    """An actor created via app1 must not be visible to app2."""
    from vultron.wire.as2.vocab.base.objects.actors import as_Service

    actor_id = "https://example.org/actors/isolated-test-actor"
    actor = as_Service(id_=actor_id, name="IsolatedTestActor")

    with TestClient(app1), TestClient(app2):
        from vultron.adapters.driven.datalayer import get_shared_dl

        dl1 = app1.dependency_overrides[get_shared_dl]()
        dl2 = app2.dependency_overrides[get_shared_dl]()

        dl1.save(actor)

        assert dl1.read(actor_id) is not None
        assert dl2.read(actor_id) is None


def test_create_app_datalayer_override_not_clobbered(app1):
    """A pre-registered dependency_overrides entry is not overwritten."""
    from vultron.adapters.driven.datalayer import get_shared_dl
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

    custom_dl = SqliteDataLayer(db_url="sqlite:///:memory:")
    app1.dependency_overrides[get_shared_dl] = lambda: custom_dl

    with TestClient(app1):
        resolved = app1.dependency_overrides[get_shared_dl]()
        assert resolved is custom_dl


def test_create_app_per_app_dispatcher_on_state(app1):
    """create_app() lifespan stores a dispatcher on app.state.dispatcher."""
    with TestClient(app1):
        d = getattr(app1.state, "dispatcher", None)
        assert d is not None
        assert hasattr(d, "dispatch") and callable(d.dispatch)


def test_create_app_does_not_mutate_global_dispatcher(app1):
    """create_app() lifespan must not overwrite the module-level _DISPATCHER."""
    original = ih._DISPATCHER

    with TestClient(app1):
        assert ih._DISPATCHER is original


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
    from vultron.adapters.driven.datalayer import get_shared_dl

    with TestClient(app1):
        pass

    assert app1.state.emitter is None
    assert app1.state.dispatcher is None
    assert getattr(app1.state, "shared_dl", None) is None
    assert get_shared_dl not in app1.dependency_overrides
