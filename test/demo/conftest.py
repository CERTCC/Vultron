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

import logging

import pytest
from fastapi.testclient import TestClient

import vultron.demo.utils as demo_utils
from vultron.adapters.driven.datalayer_sqlite import reset_datalayer
from vultron.adapters.driving.fastapi.main import app as api_app
from vultron.adapters.driven.asgi_emitter import ASGIEmitter
from vultron.adapters.driving.fastapi.outbox_handler import get_default_emitter
from vultron.core.models.activity import VultronActivity
from test.demo._helpers import (  # noqa: F401 (re-exported for test modules)
    make_testclient_call,
)

# Eliminate wait delays in all demo tests. The FastAPI TestClient processes
# background tasks synchronously, so no sleep is needed between inbox posts
# and state checks.
demo_utils.DEFAULT_WAIT_SECONDS = 0.0

logger = logging.getLogger(__name__)


class _NullDeliveryAdapter:
    """No-op ``ActivityEmitter`` that silently drops deliveries.

    Used in tests to replace ``DeliveryQueueAdapter`` as the HTTP fallback
    inside ``ASGIEmitter``.  Demo actors use fictional URLs
    (e.g. ``https://vultron.example/users/finndervul``) that are unreachable
    in the test environment.  The default ``DeliveryQueueAdapter`` attempts
    real HTTP POST requests with a 5 s timeout and 3 retries (3.5 s of
    ``asyncio.sleep`` per recipient), which caused the integration suite to
    take 17+ minutes in CI (#527).

    Replacing the fallback with this no-op adapter eliminates all HTTP
    overhead.  The outbox pipeline (emitter → ``_is_local_recipient`` →
    fallback) is still exercised; only the unreachable HTTP delivery is
    skipped.
    """

    async def emit(
        self, activity: VultronActivity, recipients: list[str]
    ) -> None:
        logger.debug(
            "NullDeliveryAdapter: skipping HTTP delivery to %d"
            " unreachable recipient(s): %s",
            len(recipients),
            recipients,
        )


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

    After the lifespan fires, the ``ASGIEmitter``'s HTTP fallback adapter is
    replaced with a ``_NullDeliveryAdapter`` that silently drops deliveries.
    Demo actors use fictional URLs
    (e.g. ``https://vultron.example/users/finndervul``) that are unreachable
    in the test environment.  The default ``DeliveryQueueAdapter`` retries
    3 × with exponential backoff (≈ 3.5 s per recipient), causing 17+ min
    CI slowdowns (#527).  The no-op adapter eliminates that overhead.

    .. note::

       The lifespan-configured ``ASGIEmitter`` uses the config default
       ``base_url`` (``http://localhost:7999``), while TestClient creates
       actor IDs under ``http://testserver``.  This means
       ``_is_local_recipient`` classifies test actors as non-local, so
       their deliveries also flow through the fallback adapter.
       Aligning the ``base_url`` would enable ASGI delivery for test
       actors, but the demo workflow tests currently assume no
       inter-actor delivery occurs (state changes are driven by
       explicit trigger-endpoint calls).  Enabling ASGI delivery is
       deferred until the test fixtures support it (#530).

    See also: #530 (actors sharing a single DataLayer in tests — a separate
    correctness bug).
    """
    with TestClient(api_app) as test_client:
        # Replace the HTTP fallback with a no-op adapter.  All non-local
        # deliveries (both fictional demo hosts and testserver-based test
        # actors) are silently dropped.  See docstring note above for why
        # test actors are also classified as non-local.
        emitter = get_default_emitter()
        if isinstance(emitter, ASGIEmitter):
            emitter._http_fallback = _NullDeliveryAdapter()  # type: ignore[assignment]
        yield test_client
