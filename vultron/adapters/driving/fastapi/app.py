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


def _auto_inject_isolated_datalayer(application: FastAPI) -> None:
    """Auto-inject an in-memory DataLayer if none is already registered.

    Called during :func:`_make_lifespan` startup when ``configure_globals``
    is ``False``.  If the caller has already registered an override (e.g. a
    test fixture's ``SqliteDataLayer``), it is left untouched.  Otherwise a
    fresh in-memory database is created and stored on ``app.state.shared_dl``
    so it can be closed on shutdown.
    """
    from vultron.adapters.driven.datalayer import get_shared_dl

    if get_shared_dl in application.dependency_overrides:
        return

    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

    isolated_dl = SqliteDataLayer(db_url="sqlite:///:memory:")
    application.dependency_overrides[get_shared_dl] = lambda: isolated_dl
    application.state.shared_dl = isolated_dl


def _teardown_per_app_state(application: FastAPI) -> None:
    """Clean up per-app dispatcher and DataLayer state on lifespan shutdown."""
    from vultron.adapters.driven.datalayer import get_shared_dl

    application.state.dispatcher = None
    dl_to_close = getattr(application.state, "shared_dl", None)
    if dl_to_close is None:
        return
    application.state.shared_dl = None
    if get_shared_dl in application.dependency_overrides:
        del application.dependency_overrides[get_shared_dl]
    dl_to_close.close()


def _make_lifespan(
    *, configure_globals: bool = True, mount_prefix: str = "/api/v2"
):
    """Return a lifespan context manager for a FastAPI Vultron application.

    Args:
        configure_globals: When ``True`` (the default for the production
            singleton ``app_v2``), the lifespan installs the
            ``ASGIEmitter`` as the module-level default emitter, configures
            logging, and starts the background ``OutboxMonitor``.  When
            ``False`` (used by :func:`create_app` for isolated test apps),
            these global side-effects are skipped so that multiple apps
            running in the same process do not contaminate each other's
            state.
        mount_prefix: URL prefix at which the app's routes are mounted.
            ``app_v2`` (the production singleton) is mounted at
            ``/api/v2`` by the root app, so the emitter must strip that
            prefix from recipient paths.  ``create_app()`` apps include
            the router *with* the ``/api/v2`` prefix, so their emitter
            should use ``""`` to avoid double-stripping.
    """

    @asynccontextmanager
    async def _lifespan(application: FastAPI):
        if configure_globals:
            configure_logging()

        from vultron.adapters.driven.asgi_emitter import ASGIEmitter
        from vultron.adapters.driving.fastapi.inbox_handler import (
            init_dispatcher,
            make_dispatcher,
        )

        if configure_globals:
            init_dispatcher()
        else:
            application.state.dispatcher = make_dispatcher()

        emitter = ASGIEmitter(app=application, mount_prefix=mount_prefix)
        application.state.emitter = emitter

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

            configure_default_emitter(emitter)
            monitor = OutboxMonitor()
            monitor.start()

        yield

        if monitor is not None:
            monitor.stop()
        # Remove the per-app emitter reference so a stale ASGIEmitter
        # cannot leak between TestClient lifetimes on the same app
        # singleton (e.g. unit tests followed by integration tests).
        application.state.emitter = None

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
app_v2.include_router(router)


def create_app(
    title: str = "Vultron API v2",
    version: str = "0.2.0",
    docs_url: str | None = "/docs",
    openapi_url: str | None = "/openapi/v2.json",
) -> FastAPI:
    """Factory that creates a fresh, isolated FastAPI application instance.

    Each call produces an independent application with its own lifespan
    context.  During startup the lifespan automatically:

    - Creates a per-app inbox dispatcher (stored on ``app.state.dispatcher``)
      so that multiple ``create_app()`` instances in the same process never
      share the module-level ``_DISPATCHER`` global (issue #534).
    - Injects a fresh in-memory ``SqliteDataLayer`` via
      ``app.dependency_overrides[get_shared_dl]`` when no override has
      already been registered, giving each instance its own isolated
      storage (issue #534).

    If you need a specific DataLayer (e.g. a file-backed SQLite database or
    a test-fixture instance), register the override *before* the lifespan
    starts (i.e. before calling ``TestClient.__enter__()``):

    .. code-block:: python

        app = create_app(docs_url=None, openapi_url=None)
        app.dependency_overrides[get_shared_dl] = lambda: my_dl
        with TestClient(app) as client:
            ...

    Args:
        title: OpenAPI title.
        version: OpenAPI version string.
        docs_url: URL for the Swagger UI (``None`` to disable).
        openapi_url: URL for the OpenAPI schema (``None`` to disable).

    Returns:
        A new :class:`FastAPI` instance with the Vultron router included.
    """
    from vultron.config import RunMode, get_config  # noqa: E402

    application = FastAPI(
        title=title,
        version=version,
        docs_url=docs_url,
        openapi_url=openapi_url,
        lifespan=_make_lifespan(configure_globals=False, mount_prefix=""),
    )
    application.include_router(router, prefix="/api/v2")
    if get_config().mode == RunMode.PROTOTYPE:
        from vultron.adapters.driving.fastapi.routers import demo_triggers

        application.include_router(demo_triggers.router, prefix="/api/v2")
    return application


# Demo-only endpoints are mounted conditionally so they never appear in
# production deployments (TRIG-09-002, TRIG-09-003).
from vultron.config import RunMode, get_config  # noqa: E402

if get_config().mode == RunMode.PROTOTYPE:
    from vultron.adapters.driving.fastapi.routers import demo_triggers

    app_v2.include_router(demo_triggers.router)
