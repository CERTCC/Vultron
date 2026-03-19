#!/usr/bin/env python
"""
Vultron API Application
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

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from vultron.adapters.driving.fastapi.app import app_v2

#
# from api.v2.app import app_v2


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Root app lifespan — runs startup tasks not covered by sub-app lifespans.

    Starlette does not automatically propagate lifespan events to mounted
    sub-applications, so any initialisation that must run before the first
    request (e.g. the inbox dispatcher) is performed here as well as in the
    ``app_v2`` lifespan (which fires when that sub-app is used directly,
    e.g. in unit tests targeting ``app_v2`` directly).
    """
    from vultron.adapters.driving.fastapi.inbox_handler import init_dispatcher
    from vultron.adapters.driven.datalayer_tinydb import get_datalayer

    init_dispatcher(dl=get_datalayer())
    yield


app = FastAPI(
    title="Vultron API Home",
    docs_url=None,  # disable default docs
    redoc_url=None,
    lifespan=lifespan,
)

app.mount("/api/v2", app_v2)


# Simple HTML landing page
@app.get("/docs", response_class=HTMLResponse)
async def custom_docs_home():
    return """
    <html>
      <head><title>API Documentation</title></head>
      <body>
        <h1>API Documentation</h1>
        <ul>
          <li><a href="/api/v2/docs">v2 Docs</a></li>
        </ul>
      </body>
    </html>
    """


# root should redirect to docs
# at least until we have something better to show
@app.get("/", include_in_schema=False, description="Redirect to API docs")
async def redirect_root_to_docs():
    return RedirectResponse(url="/docs")


def main():
    from fastapi.routing import APIRoute, Mount

    routes_by_tag = dict()

    def collect_routes(app_routes, prefix=""):
        for route in app_routes:
            if isinstance(route, Mount):
                # Recursively process mounted apps
                mounted_prefix = prefix + route.path
                collect_routes(route.app.routes, mounted_prefix)
            elif isinstance(route, APIRoute):
                # Add prefix to the route path
                full_path = prefix + route.path

                if not route.tags:
                    route.tags = ["default"]

                for tag in route.tags:
                    if tag not in routes_by_tag:
                        routes_by_tag[tag] = []
                    routes_by_tag[tag].append((route, full_path))

    # Start collecting routes from the main app
    collect_routes(app.routes)

    # Print the collected routes
    for tag, route_data in routes_by_tag.items():
        print(f"## Tag: {tag}")
        print()

        print("| Endpoint | Description |")
        print("|:---------|:------------|")
        line_format = "| `{method} {path}` | {description} |"

        for route, full_path in route_data:
            for method in route.methods:
                print(
                    line_format.format(
                        method=method,
                        path=full_path,
                        description=route.description or "No description",
                    )
                )
        print()


if __name__ == "__main__":
    main()
