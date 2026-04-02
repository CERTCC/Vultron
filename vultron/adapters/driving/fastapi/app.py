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
import os
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
    log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
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


@asynccontextmanager
async def lifespan(application: FastAPI):
    configure_logging()
    from vultron.adapters.driving.fastapi.inbox_handler import init_dispatcher
    from vultron.adapters.driven.datalayer_tinydb import get_datalayer

    init_dispatcher(dl=get_datalayer())
    yield


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
    lifespan=lifespan,
)
app_v2.include_router(router)
