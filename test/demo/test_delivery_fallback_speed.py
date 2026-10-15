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

"""Regression test for #527: delivery to unreachable hosts must not block tests.

Demo actors use fictional URLs (e.g. ``https://vultron.example/...``) that
cannot be reached via HTTP.  The default ``HttpDeliveryAdapter`` would
attempt real HTTP POST requests with 3 retries and exponential backoff
(≈ 3.5 s per recipient), which caused the integration suite to take 17+
minutes in CI.

This test verifies that the conftest replaces the default emitter with a
``_TestClientRouter`` so that deliveries to unreachable hosts complete in
under 8 seconds.
"""

import time

import pytest
from fastapi.testclient import TestClient

from test.demo._helpers import route_exchange_demo_at_testclient
from vultron.demo.exchange import receive_report_demo as demo


@pytest.fixture(scope="module")
def demo_env(client: TestClient):
    """Route the demo's clients, the runner's included, at the TestClient.

    The finder submits through its own trigger (#4675), and ``ActorSession``
    refuses a client whose base URL does not host the actor (DEMOMA-26-002),
    so the runner's client must be built at the test server's base too.
    """
    with route_exchange_demo_at_testclient(client, demo):
        yield


@pytest.mark.timeout(10)
def test_demo_completes_under_8_seconds(demo_env, caplog):
    """A single demo workflow must complete in < 8 s (#527, #2738).

    The ``demo_validate_report`` flow creates actors, submits a report, and
    validates it — exercising several inbox → outbox → delivery cycles.

    Without the conftest null-emitter patch, each delivery to an unreachable
    host (``vultron.example``) burns ≈ 3.5 s of ``asyncio.sleep`` retries.
    A single demo function hits 4+ deliveries, so baseline is ≈ 14 s.

    With the patch, the emitter drops unknown recipients.  The demo takes
    ≈ 5 s of genuine computation (BT execution, SQLite, inbox round-trips,
    actor provisioning).  The 8 s ceiling gives headroom for full-suite load
    while remaining well below the unpatched ≈ 14 s baseline; the
    ``@pytest.mark.timeout(10)`` backstop catches the regression where the
    patch is entirely absent.
    """
    import logging

    start = time.monotonic()
    with caplog.at_level(logging.ERROR):
        demo.main(skip_health_check=True, demos=[demo.demo_validate_report])
    elapsed = time.monotonic() - start

    assert "ERROR SUMMARY" not in caplog.text, (
        f"Demo failed with errors:\n{caplog.text}"
    )
    assert elapsed < 8.0, (
        f"Demo took {elapsed:.1f}s — delivery to unreachable hosts is not"
        f" patched.  Expected < 8 s with the conftest _TestClientRouter."
    )
