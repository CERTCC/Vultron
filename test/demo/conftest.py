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

import functools
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import logging

import anyio.to_thread
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import vultron.demo.utils as demo_utils
from vultron.adapters.driven.datalayer import get_shared_dl
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driving.fastapi.app import create_app
from vultron.adapters.driving.fastapi.main import app as api_app
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


class _TestClientRouter:
    """Cross-app delivery adapter for isolated multi-actor test setups.

    Routes outbound activity delivery to the correct actor app based on the
    recipient's base URL, POSTing to that app's :class:`TestClient` inbox
    endpoint.  Install via ``configure_default_emitter`` so that when Actor A
    delivers to a recipient hosted on Actor B's app, the activity is routed
    to Actor B's ``TestClient`` — the only sanctioned in-process transport
    (ADR-0042, ``outbox.yaml`` OX-12-003) — instead of a real HTTP request.

    Use :meth:`register` to map base URLs to their ``TestClient`` instances
    after entering each client's context (the ``TestClient`` must be entered so
    its portal is live before any delivery is routed to it).

    .. note::

       ``emit()`` runs inside a FastAPI ``BackgroundTask`` on the *sending*
       app's ``TestClient`` portal event loop.  The target ``TestClient.post``
       call is blocking and drives the target app on its own portal thread, so
       it is dispatched via :func:`anyio.to_thread.run_sync` to avoid blocking
       (and, for CaseActor ``cc:``-to-self loopback delivery where sender and
       target share one portal, deadlocking) the calling event loop.
    """

    def __init__(self) -> None:
        self._clients: dict[str, "TestClient"] = {}

    def register(self, base_url: str, client: "TestClient") -> None:
        """Register *client* as the delivery target for *base_url*."""
        self._clients[base_url.rstrip("/")] = client

    async def emit(
        self, activity: VultronActivity, recipients: list[str]
    ) -> None:
        """Deliver *activity* to each recipient via the registered client."""
        # serialize_as_any=True mirrors the production HttpDeliveryAdapter so
        # inline nested-object subtype fields
        # (e.g. a CaseLedgerEntry's case_id/event_type) survive the wire hop
        # between isolated apps — otherwise this test double would silently
        # drop them and mask SYNC-02-004 / SYNC-13-004 regressions.
        json_body: str = activity.model_dump_json(
            by_alias=True, exclude_none=True, serialize_as_any=True
        )
        for recipient_id in recipients:
            parsed = urlparse(recipient_id.rstrip("/") + "/inbox/")
            base = f"{parsed.scheme}://{parsed.netloc}"
            client = self._clients.get(base)
            if client is None:
                logger.debug(
                    "_TestClientRouter: no client registered for %s,"
                    " dropping delivery to %s",
                    base,
                    recipient_id,
                )
                continue
            inbox_path = parsed.path
            try:
                # TestClient.post is blocking and drives the target app on its
                # own portal thread; run it off the calling event loop so a
                # loopback delivery (sender == target) cannot deadlock.
                post = functools.partial(
                    client.post,
                    inbox_path,
                    content=json_body,
                    headers={"Content-Type": "application/json"},
                )
                response = await anyio.to_thread.run_sync(post)
                response.raise_for_status()
                logger.info(
                    "_TestClientRouter: delivered to %s (HTTP %s)",
                    inbox_path,
                    response.status_code,
                )
            except Exception as exc:
                logger.warning(
                    "_TestClientRouter: delivery to %s failed: %s",
                    inbox_path,
                    exc,
                )


@dataclass
class IsolatedActorApp:
    """Holds a FastAPI app and TestClient pair with isolated per-actor state.

    Each ``IsolatedActorApp`` instance represents a separate logical actor
    container in tests.  The ``app`` has its own ``DataLayer`` injected via
    ``dependency_overrides`` and its own ``HttpDeliveryAdapter`` stored on
    ``app.state.emitter``, so no state leaks between actors.

    Attributes:
        app: The FastAPI application instance for this actor.
        client: A ``TestClient`` wrapping ``app`` with a deterministic
            ``base_url`` (e.g. ``http://actor-name.test``).
        dl: The isolated in-memory ``SqliteDataLayer`` for this actor.
        base_url: The base URL used to construct actor IDs.
    """

    app: FastAPI
    client: TestClient
    dl: SqliteDataLayer
    base_url: str


def create_isolated_actor_app(
    base_url: str,
    router: "_TestClientRouter",
) -> "IsolatedActorApp":
    """Create an isolated FastAPI app for a single actor in tests.

    Creates a fresh :class:`FastAPI` application via :func:`create_app`,
    injects an in-memory :class:`SqliteDataLayer` via ``dependency_overrides``,
    and registers the app with the shared :class:`_TestClientRouter` so that
    deliveries to this actor are routed to its ``TestClient`` inbox instead of
    making real HTTP requests (ADR-0042, OX-12-003).

    The actor's ``TestClient`` is registered with *router* under *base_url*.
    The client reference is stable, but callers MUST enter its context
    (``with iso.client``) before any delivery is routed to it so its portal is
    live.

    Args:
        base_url: Base URL for this actor (e.g. ``"http://finder.test"``).
            Actor IDs will use this as their URL prefix.
        router: Shared :class:`_TestClientRouter` instance that all apps
            register with so cross-app deliveries are routed correctly.

    Returns:
        An :class:`IsolatedActorApp` whose ``client`` context manager has
        *not* been entered yet — callers must use it as a context manager.
    """
    isolated_dl = SqliteDataLayer(db_url="sqlite:///:memory:")
    app = create_app(docs_url=None, openapi_url=None)
    app.dependency_overrides[get_shared_dl] = lambda: isolated_dl
    # TestClient is not yet entered; the caller drives the lifecycle.
    client = TestClient(app, base_url=base_url)
    router.register(base_url, client)
    return IsolatedActorApp(
        app=app, client=client, dl=isolated_dl, base_url=base_url
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


_CASE_ACTOR_SERVICE_URL = "http://localhost:7999/api/v2"


@pytest.fixture(scope="session", autouse=True)
def configure_case_actor_url_for_demo():
    """Set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL for all demo tests.

    ResolveCaseActorUrlsNode returns FAILURE when case_actor_service_url
    is None (CP-08-002/003).  Demo tests run the engage-case BT path, so
    they need the URL configured to reach the case-setup success branch.
    """
    from vultron.config import config_override

    with config_override(
        VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL=_CASE_ACTOR_SERVICE_URL
    ):
        yield


def config_snapshot() -> dict:
    """Return the full currently-cached config as a plain dict.

    Snapshotting every field rather than a hand-picked pair means a fixture
    that leaks something other than the two #2086 URLs (e.g.
    ``VULTRON_ACTOR__DEFAULT_CASE_ROLES``) is still detected.
    """
    from vultron.config import get_config

    return get_config().model_dump(mode="json")


def config_url_snapshot() -> tuple[str, str]:
    """Return the currently cached ``(server.base_url, case_actor_service_url)``.

    These are the two settings demo tests repoint at their own fake hosts, and
    the pair whose leakage caused #2086.  Kept as a narrow, readable accessor
    for tests that assert specifically on those URLs;
    :func:`config_snapshot` is what the leak guard compares.
    """
    from vultron.config import get_config

    cfg = get_config()
    return (
        str(cfg.server.base_url),
        str(cfg.actor.case_actor_service_url),
    )


class ConfigLeakLedger:
    """Session-wide record of config leaks the guard had to repair.

    The guard repairs leaks so that one misordered teardown cannot cascade into
    unrelated failures.  That repair also hides the leak, which would leave the
    ``monkeypatch.undo()``-before-``reload_config()`` fixes in the demo modules
    unenforced by any test.  Recording each detection here keeps the repair
    while still giving :mod:`test.demo.test_config_leak_guard` something that
    fails when a fixture teardown regresses (#2086).
    """

    def __init__(self) -> None:
        self.leaks: list[str] = []

    def record(self, before: dict, after: dict) -> None:
        self.leaks.append(f"{_describe_drift(before, after)}")

    def reset(self) -> None:
        self.leaks.clear()


#: Session-wide ledger; asserted on by ``test_config_leak_guard.py``.
config_leak_ledger = ConfigLeakLedger()


def _describe_drift(before: dict, after: dict) -> str:
    """Summarise which config keys changed, for logs and assertion messages."""
    drifted = sorted(
        f"{key}: {before.get(key)!r} -> {after.get(key)!r}"
        for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    )
    return "; ".join(drifted)


def restore_config_if_leaked(before: dict) -> bool:
    """Reload the module-level config if it drifted from the *before* snapshot.

    The repair is :func:`reload_config`, which re-reads ``os.environ``.  That
    only helps if the offending fixture also undid its env patches, so the
    post-reload state is verified rather than assumed: a reload that fails to
    restore *before* raises instead of reporting a success it did not achieve
    (ARCH-15-001 — a fake success is the same bug as a silent ``None``).

    Args:
        before: Snapshot from :func:`config_snapshot` taken before the code
            under test ran.

    Returns:
        ``True`` if a leak was detected and successfully repaired, ``False``
        if the config never drifted.

    Raises:
        RuntimeError: if the config drifted and the reload did not restore it,
            which means the environment itself is still polluted.
    """
    from vultron.config.app import reload_config

    after = config_snapshot()
    if after == before:
        return False

    drift = _describe_drift(before, after)
    logger.warning(
        "Demo test leaked config (%s); reloading (#2086)",
        drift,
    )
    config_leak_ledger.record(before, after)
    reload_config()

    repaired = config_snapshot()
    if repaired != before:
        raise RuntimeError(
            "Config leak could not be repaired by reload_config(): the "
            "environment is still polluted. A fixture mutated the "
            "environment without undoing it (see #2086). Residual drift: "
            f"{_describe_drift(before, repaired)}"
        )
    return True


@pytest.fixture(autouse=True)
def restore_case_actor_url_after_each_test():
    """Restore the session's CaseActor/server config after every demo test.

    Guards against config leakage between demo tests (#2086).  Several demo
    tests point ``VULTRON_SERVER__BASE_URL`` and
    ``VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL`` at their own fake hosts and then
    call ``reload_config()``.  If such a test reloads while its env patches are
    still applied, the polluted values are cached in the module-level config for
    the remainder of the session.  Every later test then addresses its
    ``Create(CaseProposal)`` to a host no ``_TestClientRouter`` knows about, the
    delivery is silently dropped, the CaseActor never creates the canonical
    case, and ``validate-report`` fails with "no routable recipients".

    Because that depends on test *order*, it presented as CI flakiness.  This
    fixture snapshots the config before each test and reloads after if it
    drifted.

    **Scope limitation**: this fixture is function-scoped, so it only catches
    *function-scoped* offenders.  A module-, class-, or session-scoped fixture
    pollutes the cache *before* this guard takes its ``before`` snapshot, so
    the drift is invisible here and that fixture's teardown runs after this
    one's finalizer.  Higher-scoped fixtures must therefore still order
    ``monkeypatch.undo()`` before ``reload_config()`` themselves — the guard is
    not a substitute.  Any repair performed here is recorded on
    :data:`config_leak_ledger` so ``test_config_leak_guard.py`` fails rather
    than silently masking the regression.
    """
    before = config_snapshot()
    yield
    restore_config_if_leaked(before)


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

    After the lifespan fires, the module-level default emitter is replaced
    with a ``_TestClientRouter`` that routes all actor URLs hosted on
    ``api_app`` back to *test_client* (so cc:-to-self loopback deliveries work
    in-process), while silently dropping deliveries to fictional external URLs
    (e.g. ``https://vultron.example/users/...``) that are unreachable in the
    test environment.  Without this, the ``HttpDeliveryAdapter`` on
    ``api_app.state.emitter`` would attempt real HTTP POST requests with
    retries, which caused the integration suite to take 17+ min in CI (#527).

    Both the module-level default emitter (used by trigger-endpoint
    BackgroundTasks) *and* ``api_app.state.emitter`` (used by inbox-endpoint
    BackgroundTasks) are replaced, so all outbox drains route through the
    same ``_TestClientRouter``.

    See also: #530 (actors sharing a single DataLayer in tests).
    """
    from vultron.adapters.driving.fastapi.outbox_handler import (
        configure_default_emitter,
    )

    with TestClient(api_app) as test_client:
        # Build a router that routes deliveries back to the single app and
        # drops anything sent to external fictional URLs.
        router = _TestClientRouter()
        # Register both the TestClient's base_url (http://testserver) and the
        # config's server base_url (e.g. http://localhost:7999) so that all
        # actor IDs hosted on api_app — regardless of which base URL was used
        # to construct them — route back to this TestClient.
        from urllib.parse import urlparse as _urlparse
        from vultron.config import get_config

        tc_base = str(test_client.base_url).rstrip("/")
        router.register(tc_base, test_client)
        cfg_base_url = get_config().server.base_url
        if cfg_base_url:
            parsed = _urlparse(str(cfg_base_url))
            cfg_netloc_base = f"{parsed.scheme}://{parsed.netloc}"
            if cfg_netloc_base != tc_base:
                router.register(cfg_netloc_base, test_client)

        previous_emitter = get_default_emitter()
        previous_app_emitter = getattr(api_app.state, "emitter", None)
        configure_default_emitter(router)  # type: ignore[arg-type]
        api_app.state.emitter = router  # type: ignore[assignment]
        try:
            yield test_client
        finally:
            configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
            api_app.state.emitter = previous_app_emitter
