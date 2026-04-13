#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

"""Shared fixtures and helpers for demo tests."""

import pytest
from fastapi.testclient import TestClient

import vultron.demo.utils as demo_utils
from vultron.adapters.driven.datalayer_tinydb import reset_datalayer
from vultron.adapters.driving.fastapi.main import app as api_app
from test.demo._helpers import (  # noqa: F401 (re-exported for test modules)
    make_testclient_call,
)

# Eliminate wait delays in all demo tests. The FastAPI TestClient processes
# background tasks synchronously, so no sleep is needed between inbox posts
# and state checks.
demo_utils.DEFAULT_WAIT_SECONDS = 0.0


def pytest_collection_modifyitems(
    items: list[pytest.Item], config: pytest.Config
) -> None:
    """Mark every test collected from test/demo/ as ``integration``.

    Demo tests spin up a full FastAPI ASGI app via ``TestClient`` and exercise
    end-to-end HTTP request / DataLayer workflows.  They are integration tests
    by nature and should be labelled accordingly so callers can include or
    exclude them explicitly::

        # Run only integration tests
        uv run pytest -m integration

        # Run everything
        uv run pytest -m ""

    This hook runs after collection so it applies regardless of how the tests
    are selected (e.g. ``pytest test/demo/`` or ``pytest`` from the root).
    """
    for item in items:
        if "/test/demo/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="module", autouse=True)
def reset_datalayer_between_modules():
    """Reset all cached DataLayer instances before each demo test module.

    Demo tests create actors, reports, and cases via the API.  Without a
    reset between modules the shared in-memory TinyDB accumulates data from
    every preceding module, which (a) slows later tests as the in-memory DB
    grows, and (b) can cause unexpected cross-module data visibility.

    Resetting here ensures each test module starts with an empty DataLayer.
    The ``pytest_configure`` patch in ``test/conftest.py`` guarantees that
    the fresh instance created by the first API call after the reset will use
    MemoryStorage.
    """
    reset_datalayer()
    yield
    reset_datalayer()


@pytest.fixture(scope="module")
def client():
    """Provides a shared TestClient instance for demo tests in this module.

    Uses the context-manager form so the FastAPI lifespan events (startup and
    shutdown) are triggered, which initialises the inbox dispatcher via
    :func:`vultron.adapters.driving.fastapi.inbox_handler.init_dispatcher`.
    """
    with TestClient(api_app) as test_client:
        yield test_client
