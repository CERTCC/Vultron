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

"""Regression test for #531: ASGIEmitter reentrancy guard.

Verifies that ``ASGIEmitter._try_deliver_local`` does not recurse within
the same asyncio task.  When already inside a delivery chain, subsequent
calls return ``False`` (deferring to the HTTP fallback) instead of
creating nested ``ASGITransport`` calls that deadlock the event loop.
"""

import asyncio

import pytest

from vultron.adapters.driven.asgi_emitter import (
    ASGIEmitter,
    _asgi_delivery_depth,
)


@pytest.fixture(autouse=True)
def _reset_delivery_depth():
    """Ensure the delivery depth context var starts at 0."""
    token = _asgi_delivery_depth.set(0)
    yield
    _asgi_delivery_depth.reset(token)


class TestReentrancyGuard:
    """Tests for the ASGI delivery reentrancy guard (#531)."""

    def test_skips_delivery_when_depth_positive(self):
        """_try_deliver_local returns False when already in a chain."""

        async def _run() -> bool:
            token = _asgi_delivery_depth.set(1)
            try:
                emitter = ASGIEmitter.__new__(ASGIEmitter)
                return await emitter._try_deliver_local(
                    json_body='{"type": "Create"}',
                    recipient_id="http://localhost/actors/test",
                    activity_id="urn:test:1",
                )
            finally:
                _asgi_delivery_depth.reset(token)

        result = asyncio.run(_run())
        assert result is False

    def test_depth_starts_at_zero(self):
        """Default delivery depth is 0 (no active chain)."""
        assert _asgi_delivery_depth.get() == 0
