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

from fastapi import FastAPI

from .routers import router

# Get Uvicorn's root logger and configure handlers
uvicorn_logger = logging.getLogger("uvicorn")
logging.getLogger().handlers = uvicorn_logger.handlers
logging.getLogger().setLevel(logging.DEBUG)

# Optionally, unify FastAPI’s access and error logs as well
logging.getLogger("uvicorn.access").propagate = True
logging.getLogger("uvicorn.error").propagate = True

# Create your logger for your app
logger = logging.getLogger(__name__)


tags_metadata = [
    {
        "name": "Examples",
        "description": """Actors have inboxes. You can get an example Actor object or validate one.
For convenience, we also provide an example Note object and validation endpoint.
        
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
)
app_v2.include_router(router)
