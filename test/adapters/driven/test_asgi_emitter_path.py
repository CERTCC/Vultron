#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute
#  to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Regression tests for #557/#558: ASGIEmitter path double-prefix bug.

When the production server mounts ``app_v2`` at ``/api/v2``, the
``ASGIEmitter`` is configured with ``base_url="http://host:port/api/v2"``
and ``mount_prefix="/api/v2"``.  The emitter strips the mount prefix from
the recipient path *before* handing it to httpx, but then constructs the
httpx client with the full ``base_url`` (including the ``/api/v2`` path
component).  Because httpx *appends* a relative path to the base URL path
segment, the path reaching the ASGI sub-app becomes
``/api/v2/actors/{id}/inbox/`` instead of ``/actors/{id}/inbox/``, which
does not match any route and returns HTTP 404.

The fix is to use only the scheme+netloc (no path component) as the
``base_url`` for the httpx ASGI transport client.
"""

import asyncio
from typing import cast

from fastapi import FastAPI


def _make_stub_subapp(received_actor_ids: list[str]) -> FastAPI:
    """Return a minimal FastAPI sub-app that mirrors ``app_v2``'s route layout.

    Routes are registered *without* a ``/api/v2`` prefix, exactly as
    ``app_v2`` is configured in production (the prefix is added by the
    root app's ``Mount`` wrapper).
    """
    subapp = FastAPI()

    @subapp.post("/actors/{actor_id}/inbox/")
    async def inbox(actor_id: str) -> dict[str, str]:
        received_actor_ids.append(actor_id)
        return {"actor_id": actor_id}

    return subapp


class TestASGIEmitterPathDelivery:
    """Tests for correct path construction in ASGIEmitter ASGI delivery.

    Regression coverage for GitHub issues #557 and #558.
    """

    def test_delivers_to_subapp_with_mount_prefix(self):
        """ASGI delivery reaches the sub-app route when mount_prefix is set.

        Reproduces the bug: with ``base_url="http://testserver/api/v2"`` and
        ``mount_prefix="/api/v2"``, the path sent to the sub-app was
        ``/api/v2/actors/{id}/inbox/`` (double prefix) → 404.

        After the fix the path is ``/actors/{id}/inbox/`` → 200.
        """
        from vultron.adapters.driven.asgi_emitter import ASGIEmitter

        received: list[str] = []
        subapp = _make_stub_subapp(received)

        emitter = ASGIEmitter(
            app=subapp,
            base_url="http://testserver/api/v2",
            mount_prefix="/api/v2",
        )

        async def _run() -> bool:
            return cast(
                bool,
                await emitter._try_deliver_local(
                    json_body='{"type": "Offer", "id": "urn:test:1"}',
                    recipient_id="http://testserver/api/v2/actors/case-actor-abc",
                    activity_id="urn:test:1",
                ),
            )

        result = asyncio.run(_run())
        assert result is True, (
            "ASGI delivery returned False — route not matched "
            "(double mount-prefix bug still present)"
        )
        assert received == [
            "case-actor-abc"
        ], f"Expected case-actor-abc in inbox, got {received}"

    def test_delivers_to_subapp_without_mount_prefix(self):
        """ASGI delivery reaches the sub-app when mount_prefix is empty.

        This covers ``create_app()``-style apps where the router is included
        with the ``/api/v2`` prefix baked in, and the emitter uses
        ``mount_prefix=""``.
        """
        from vultron.adapters.driven.asgi_emitter import ASGIEmitter

        received: list[str] = []

        # Simulate create_app(): routes have /api/v2 prefix
        app_with_prefix = FastAPI()

        @app_with_prefix.post("/api/v2/actors/{actor_id}/inbox/")
        async def inbox(actor_id: str) -> dict[str, str]:
            received.append(actor_id)
            return {"actor_id": actor_id}

        emitter = ASGIEmitter(
            app=app_with_prefix,
            base_url="http://testserver/api/v2",
            mount_prefix="",
        )

        async def _run() -> bool:
            return cast(
                bool,
                await emitter._try_deliver_local(
                    json_body='{"type": "Offer", "id": "urn:test:2"}',
                    recipient_id="http://testserver/api/v2/actors/vendor",
                    activity_id="urn:test:2",
                ),
            )

        result = asyncio.run(_run())
        assert result is True, (
            "ASGI delivery returned False — route not matched "
            "(no-prefix case broken)"
        )
        assert received == ["vendor"]
