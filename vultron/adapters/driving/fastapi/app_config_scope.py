#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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

"""Run each request to an app in that app's config scope (ADR-0206).

An app made by ``create_app(config=...)`` holds its own ``AppConfig``.  The
middleware here enters ``app_config_scope`` for every HTTP and WebSocket
request the app serves, so ``get_config()`` and ``load_actor_config()`` read
that config with no change at the places that call them.  An app that holds
no config enters the process-wide scope instead.

The lifespan scope is entered by the app's lifespan, not here, because the
lifespan also counts the app as running (``holding_app_config``).
"""

from starlette.types import ASGIApp, Receive, Scope, Send

from vultron.config import AppConfig, app_config_scope


class AppConfigScopeMiddleware:
    """Pure ASGI middleware that runs each request in its app's config scope.

    A pure ASGI middleware rather than ``BaseHTTPMiddleware``, so the scope is
    a context variable set in the task that runs the endpoint, its
    dependencies, a sync endpoint's worker thread (``anyio`` copies the
    context into it) and the response's ``BackgroundTasks``.

    Args:
        app: The ASGI app it wraps.
        config: The app's own config, or ``None`` for an app that has none.
    """

    def __init__(self, app: ASGIApp, config: AppConfig | None) -> None:
        self.app = app
        self.config = config

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        with app_config_scope(self.config):
            await self.app(scope, receive, send)
