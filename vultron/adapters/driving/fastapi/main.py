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

from enum import Enum
from typing import Any, cast

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute, Mount

from vultron.adapters.driving.fastapi.app import _make_lifespan, app_v2

#
# from api.v2.app import app_v2


#: Root app lifespan.  Starlette does not propagate lifespan events to a
#: mounted sub-application, so the process-level startup that ``app_v2``'s own
#: lifespan performs when that sub-app is served directly — logging, the inbox
#: dispatcher, the default ``HttpDeliveryAdapter``, the ``OutboxMonitor``
#: safety-net drain (OX-09-002) and the pending ``Create(VulnerabilityCase)``
#: retry (CP-05-005) — has to run here for the served process.  A hand-written
#: copy of that list drifted: it omitted the monitor, so no container ever ran
#: the safety-net poll, and an activity queued in an outbox no inline drain
#: was looping over waited for the next inbound activity to that actor
#: (111 s in CI run 36643399281; #3602, ADR-0112).  Sharing the factory keeps
#: the two lifespans one list.
lifespan = _make_lifespan(configure_globals=True)


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


def _route_tags(route: APIRoute) -> list[str | Enum]:
    if not route.tags:
        route.tags = cast(list[str | Enum], ["default"])
    return route.tags


def _mounted_routes(route: Mount) -> list[BaseRoute]:
    mounted_app = cast(Any, route.app)
    if not hasattr(mounted_app, "routes"):
        return []
    return cast(list[BaseRoute], mounted_app.routes)


def _collect_routes(
    app_routes: list[BaseRoute],
    routes_by_tag: dict[str | Enum, list[tuple[APIRoute, str]]],
    prefix: str = "",
) -> None:
    for route in app_routes:
        if isinstance(route, Mount):
            _collect_routes(
                _mounted_routes(route), routes_by_tag, prefix + route.path
            )
            continue
        if not isinstance(route, APIRoute):
            continue

        full_path = prefix + route.path
        for tag in _route_tags(route):
            routes_by_tag.setdefault(tag, []).append((route, full_path))


def _print_routes_by_tag(
    routes_by_tag: dict[str | Enum, list[tuple[APIRoute, str]]],
) -> None:
    line_format = "| `{method} {path}` | {description} |"
    for tag, route_data in routes_by_tag.items():
        print(f"## Tag: {tag}")
        print()
        print("| Endpoint | Description |")
        print("|:---------|:------------|")

        for route, full_path in route_data:
            for method in route.methods or set():
                print(
                    line_format.format(
                        method=method,
                        path=full_path,
                        description=route.description or "No description",
                    )
                )
        print()


def main():
    routes_by_tag: dict[str | Enum, list[tuple[APIRoute, str]]] = {}
    _collect_routes(app.routes, routes_by_tag)
    _print_routes_by_tag(routes_by_tag)


if __name__ == "__main__":
    main()
