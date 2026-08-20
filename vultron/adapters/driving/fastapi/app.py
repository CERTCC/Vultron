#!/usr/bin/env python
"""
Vultron API v2 Application
"""

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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

import logging
from contextlib import asynccontextmanager

from uuid import uuid4

from fastapi import FastAPI

from vultron.adapters.driving.fastapi.routers import router

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure root logger to use Uvicorn's handlers at server startup.

    Reads ``LOG_LEVEL`` from the environment (default ``INFO``) and applies it
    to the root logger.  HTTP access logs (``uvicorn.access``) are suppressed
    at INFO level to reduce noise; set ``LOG_LEVEL=DEBUG`` to see them.

    Only called inside the lifespan context so importing this module in tests
    does not mutate the root logger.
    """
    from vultron.config import get_config

    log_level_name = get_config().server.log_level
    log_level = getattr(logging, log_level_name, logging.INFO)

    uvicorn_logger = logging.getLogger("uvicorn")
    logging.getLogger().handlers = uvicorn_logger.handlers
    logging.getLogger().setLevel(log_level)
    logging.getLogger("uvicorn.error").propagate = True

    # Suppress HTTP access-log entries at INFO; only surface them at DEBUG so
    # that repeated health-check and API request lines do not drown out
    # application-level log messages.
    #
    # Using NullHandler + propagate=False is more robust than setLevel() alone:
    # uvicorn may reinitialise its dictConfig after the lifespan fires (e.g.
    # with --reload), which would reset a simple setLevel() change.
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    if log_level > logging.DEBUG:
        # Replace any handlers set by uvicorn's dictConfig with a NullHandler
        # so that access-log records are silently discarded.
        uvicorn_access_logger.handlers = [logging.NullHandler()]
        uvicorn_access_logger.propagate = False
    else:
        uvicorn_access_logger.propagate = True

    # Suppress httpx library internals (request/response lifecycle events)
    # to reduce DEBUG output noise by ~30%.
    logging.getLogger("httpx2").setLevel(logging.WARNING)

    # Drop `transitions` FSM callback chatter from INFO (SL-04-007).
    from vultron.logging_setup import suppress_third_party_info_noise

    suppress_third_party_info_noise(log_level)


def _auto_inject_isolated_datalayer(application: FastAPI) -> None:
    """Auto-inject per-actor in-memory DataLayers if none are registered.

    Called during :func:`_make_lifespan` startup when ``configure_globals``
    is ``False``.  If the caller has already registered an override (e.g. a
    test fixture), it is left untouched.

    Two dimensions of isolation are in play and both must hold:

    - **Per application** (issue #534): several ``create_app()`` instances in
      one process must not share storage.  Each app therefore gets its own
      *named* in-memory deployment, so the resolved URL differs per app.
      Without the name every app would resolve to the same store and
      cross-app leakage would return — along a different axis than the one
      ADR-0066 closed, but the same class of bug.
    - **Per actor** (ADR-0066, CM-01-001): within an app, each actor gets its
      own store.  The override is therefore a *factory* keyed on the requested
      actor, not one shared instance.
    """
    from vultron.adapters.driving.fastapi.deps import get_actor_dl

    if get_actor_dl in application.dependency_overrides:
        return

    from fastapi import Path as _Path

    from vultron.adapters.driven.actor_hosts import canonical_actor_uri
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

    db_url = (
        f"sqlite:///file:app-{uuid4().hex}"
        "?mode=memory&cache=shared&uri=true"
    )
    registry: dict[str, SqliteDataLayer] = {}

    def _isolated_actor_dl(actor_id: str = _Path(...)) -> SqliteDataLayer:
        canonical = canonical_actor_uri(actor_id)
        if canonical not in registry:
            registry[canonical] = SqliteDataLayer(
                db_url=db_url, actor_id=canonical
            )
        return registry[canonical]

    application.dependency_overrides[get_actor_dl] = _isolated_actor_dl
    application.state.actor_dls = registry
    application.state.db_url = db_url


def _teardown_per_app_state(application: FastAPI) -> None:
    """Clean up per-app dispatcher and DataLayer state on lifespan shutdown."""
    from vultron.adapters.driving.fastapi.deps import get_actor_dl

    # Clear dispatcher BEFORE the early return: even when the DataLayers were
    # supplied by a pre-registered override (app.state.actor_dls is None),
    # the per-app dispatcher was still created by this lifespan and must be
    # released so it cannot leak across lifespan restarts on the same app.
    application.state.dispatcher = None
    registry = getattr(application.state, "actor_dls", None)
    if registry is None:
        return
    application.state.actor_dls = None
    if get_actor_dl in application.dependency_overrides:
        del application.dependency_overrides[get_actor_dl]
    # Closing every actor's store drops this app's named in-memory databases:
    # an in-memory database lives only while a connection to it is open.
    for actor_dl in registry.values():
        actor_dl.close()


def _make_lifespan(*, configure_globals: bool = True):
    """Return a lifespan context manager for a FastAPI Vultron application.

    Args:
        configure_globals: When ``True`` (the default for the production
            singleton ``app_v2``), the lifespan installs the
            ``HttpDeliveryAdapter`` as the module-level default emitter,
            configures logging, and starts the background ``OutboxMonitor``.
            When ``False`` (used by :func:`create_app` for isolated test apps),
            these global side-effects are skipped so that multiple apps
            running in the same process do not contaminate each other's state.
    """

    @asynccontextmanager
    async def _lifespan(application: FastAPI):
        if configure_globals:
            configure_logging()

        from vultron.adapters.driven.http_delivery import HttpDeliveryAdapter
        from vultron.adapters.driving.fastapi.inbox_handler import (
            init_dispatcher,
            make_dispatcher,
        )

        if configure_globals:
            init_dispatcher()
        else:
            application.state.dispatcher = make_dispatcher()

        if not configure_globals:
            _auto_inject_isolated_datalayer(application)

        monitor = None
        if configure_globals:
            from vultron.adapters.driving.fastapi.outbox_handler import (
                configure_default_emitter,
            )
            from vultron.adapters.driving.fastapi.outbox_monitor import (
                OutboxMonitor,
            )

            emitter = HttpDeliveryAdapter()
            application.state.emitter = emitter
            configure_default_emitter(emitter)
            monitor = OutboxMonitor()
            monitor.start()

            # Retry any Create(VulnerabilityCase) activities that were
            # left pending from a previous process run (CP-05-005, #1139).
            # The OutboxMonitor is started first so it can drain the
            # re-queued activities immediately after startup.
            from vultron.adapters.driving.fastapi.pending_retry import (
                retry_pending_create_case_activities,
            )

            retry_pending_create_case_activities()

        yield

        if monitor is not None:
            monitor.stop()
        # Clear the per-app emitter reference so it cannot leak between
        # TestClient lifetimes on the same app singleton.
        if configure_globals:
            application.state.emitter = None
            # configure_logging() pinned third-party logger levels globally;
            # undo it so a TestClient lifetime does not reconfigure logging
            # for everything that runs after it.
            from vultron.logging_setup import (
                restore_third_party_log_levels,
            )

            restore_third_party_log_levels()

        if not configure_globals:
            _teardown_per_app_state(application)

    return _lifespan


tags_metadata = [
    {
        "name": "Examples",
        "description": """Vocabulary showcase endpoints. Each object type has a GET endpoint
that returns a sample instance and a POST endpoint that validates a submitted
object through the Pydantic model.

- `GET` to see a sample object.
- `POST` an object to run it through the pydantic model validation.
""",
    },
    {
        "name": "Actors",
        "description": """Actors are the entities that participate in Vultron activities.
They can be individuals, organizations, or software agents.
Each Actor has an inbox where they receive activities and messages.

In a full implementation, Actors would also have outboxes for sending activities, but
for this prototype, we focus on inboxes since most Vultron interactions are done via direct
messages to an Actor's inbox.
""",
    },
]

app_v2 = FastAPI(
    title="Vultron API v2",
    version="0.2.0",
    docs_url="/docs",
    openapi_url="/openapi/v2.json",
    openapi_tags=tags_metadata,
    lifespan=_make_lifespan(configure_globals=True),
)


def create_app(
    title: str = "Vultron API v2",
    version: str = "0.2.0",
    docs_url: str | None = "/docs",
    openapi_url: str | None = "/openapi/v2.json",
    node_base_url: str | None = None,
) -> FastAPI:
    """Factory that creates a fresh, isolated FastAPI application instance.

    Each call produces an independent application with its own lifespan
    context.  During startup the lifespan automatically:

    - Creates a per-app inbox dispatcher (stored on ``app.state.dispatcher``)
      so that multiple ``create_app()`` instances in the same process never
      share the module-level ``_DISPATCHER`` global (issue #534).
    - Injects per-actor in-memory ``SqliteDataLayer`` instances via
      ``app.dependency_overrides[get_actor_dl]`` when no override has already
      been registered.  Each app gets its own *named* in-memory deployment, so
      instances never share storage (issue #534), and within an app each actor
      gets its own store (ADR-0066, CM-01-001).

    If you need specific DataLayers (e.g. file-backed SQLite, or test-fixture
    instances), register the override *before* the lifespan starts (i.e. before
    calling ``TestClient.__enter__()``).  The override receives the requested
    ``actor_id`` path segment, so it must return that actor's store:

    .. code-block:: python

        app = create_app(docs_url=None, openapi_url=None)
        app.dependency_overrides[get_actor_dl] = (
            lambda actor_id: my_dls[canonical_actor_uri(actor_id)]
        )
        with TestClient(app) as client:
            ...

    Args:
        title: OpenAPI title.
        version: OpenAPI version string.
        docs_url: URL for the Swagger UI (``None`` to disable).
        openapi_url: URL for the OpenAPI schema (``None`` to disable).
        node_base_url: Base URL at which *this* app is reached, used to resolve
            actor path segments to canonical URIs.  Leave ``None`` to use
            ``ServerConfig.base_url``, which is correct whenever one process is
            one node.  Set it when several apps run in one process and each must
            resolve segments into its own namespace — otherwise an actor created
            under one app's base URL is looked up under another's and reported
            missing.  See ``deps.node_base_url``.

    Returns:
        A new :class:`FastAPI` instance with the Vultron router included.
    """
    from vultron.config import RunMode, get_config  # noqa: E402

    application = FastAPI(
        title=title,
        version=version,
        docs_url=docs_url,
        openapi_url=openapi_url,
        lifespan=_make_lifespan(configure_globals=False),
    )
    application.state.node_base_url = node_base_url
    if get_config().mode == RunMode.PROTOTYPE:
        from vultron.adapters.driving.fastapi.routers import demo_triggers

        application.include_router(demo_triggers.router, prefix="/api/v2")
    application.include_router(router, prefix="/api/v2")
    return application


# Demo-only endpoints are mounted conditionally so they never appear in
# production deployments (TRIG-09-002, TRIG-09-003).
from vultron.config import RunMode, get_config  # noqa: E402

if get_config().mode == RunMode.PROTOTYPE:
    from vultron.adapters.driving.fastapi.routers import demo_triggers

    app_v2.include_router(demo_triggers.router)
app_v2.include_router(router)
