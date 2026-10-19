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

"""Regression test for #527: demo deliveries must not take the real HTTP path.

The default ``HttpDeliveryAdapter`` makes real HTTP POST requests with 3
retries and exponential backoff (≈ 3.5 s per unreachable recipient), which
once made the integration suite take 17+ minutes in CI.  The ``client``
fixture in ``test/demo/conftest.py`` replaces both emitter resolution paths
with a ``_TestClientRouter``, the sanctioned in-process transport (OX-12-003).

This test checks that property directly: the router carries the demo's
deliveries and the HTTP adapter never attempts one.  It used to assert an
8 s wall-clock budget instead, which honest work under ``-n`` load exceeded
(#4365, #4693).
"""

from unittest.mock import patch

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from test.demo._helpers import route_exchange_demo_at_testclient
from test.demo.conftest import _TestClientRouter
from vultron.adapters.driven.http_delivery import HttpDeliveryAdapter
from vultron.demo.exchange import receive_report_demo as demo


@pytest.fixture(scope="module")
def demo_env(client: TestClient):
    """Route the demo's clients, the runner's included, at the TestClient.

    The reporter submits through its own trigger (#4675), and ``ActorSession``
    refuses a client whose base URL does not host the actor (DEMOMA-26-002),
    so the runner's client must be built at the test server's base too.
    """
    with route_exchange_demo_at_testclient(client, demo):
        yield


def test_demo_routes_every_delivery_through_the_test_router(
    demo_env: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Every delivery in a demo workflow goes through the test router (#527).

    The ``demo_validate_report`` flow creates actors, submits a report, and
    validates it — exercising several inbox → outbox → delivery cycles.  If
    either emitter path fell back to ``HttpDeliveryAdapter``, its retry loop
    would run; a single attempt fails this test, where the old stopwatch
    budget only noticed several.
    """
    import logging

    routed: list[list[str]] = []
    http_attempts: list[str] = []
    route = _TestClientRouter.emit

    async def record_route(
        self: _TestClientRouter,
        activity_id: str,
        json_body: str,
        recipients: list[str],
    ) -> None:
        routed.append(list(recipients))
        await route(self, activity_id, json_body, recipients)

    async def record_http_attempt(
        self: HttpDeliveryAdapter,
        client: httpx.AsyncClient,
        json_body: str,
        recipient_id: str,
        activity_id: str | None,
    ) -> None:
        http_attempts.append(recipient_id)

    with (
        patch.object(_TestClientRouter, "emit", record_route),
        patch.object(
            HttpDeliveryAdapter, "_deliver_with_retry", record_http_attempt
        ),
        caplog.at_level(logging.ERROR),
    ):
        demo.main(skip_health_check=True, demos=[demo.demo_validate_report])

    assert http_attempts == [], (
        f"HttpDeliveryAdapter attempted delivery to {http_attempts}; the"
        " conftest _TestClientRouter is not installed on every emitter path."
    )
    assert "ERROR SUMMARY" not in caplog.text, (
        f"Demo failed with errors:\n{caplog.text}"
    )
    assert routed, "The demo delivered nothing through the _TestClientRouter."
