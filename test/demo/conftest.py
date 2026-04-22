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

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import vultron.demo.utils as demo_utils
from vultron.adapters.driven.datalayer_sqlite import reset_datalayer
from vultron.adapters.driving.fastapi.main import app as api_app
from test.demo._helpers import (  # noqa: F401 (re-exported for test modules)
    make_testclient_call,
)

# Eliminate wait delays in all demo tests. The FastAPI TestClient processes
# background tasks synchronously, so no sleep is needed between inbox posts
# and state checks.
demo_utils.DEFAULT_WAIT_SECONDS = 0.0


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
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
        path = Path(str(item.fspath))
        if any(
            p.name == "demo" and p.parent.name == "test" for p in path.parents
        ):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="module", autouse=True)
def reset_datalayer_between_modules():
    """Reset all cached DataLayer instances before each demo test module.

    Demo tests create actors, reports, and cases via the API.  Without a
    reset between modules, cached SQLite-backed DataLayer instances can retain
    data created by earlier demo modules, which both slows later tests and
    risks unexpected cross-module visibility.

    Resetting here ensures each module starts from a clean DataLayer cache.
    After the reset, the first API call recreates the SQLite DataLayer with a
    fresh in-memory database (``sqlite:///:memory:``), which provides module
    isolation for the demo test suite.
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
