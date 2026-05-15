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
cannot be reached via HTTP.  The ``ASGIEmitter`` correctly classifies these
as non-local and delegates to a ``DeliveryQueueAdapter`` HTTP fallback.

In production the fallback's retry/backoff (3 retries, 3.5 s sleep total
per recipient) is appropriate.  In tests it is catastrophic — the demo
test suite took 17+ minutes in CI because every outbox delivery burned
3.5 s of ``asyncio.sleep`` per unreachable recipient.

This test verifies that the conftest patches the fallback adapter so that
deliveries to unreachable hosts complete in under 1 second.
"""

import time

import pytest
from fastapi.testclient import TestClient

from test.demo._helpers import make_testclient_call
from vultron.demo.exchange import receive_report_demo as demo


@pytest.fixture(scope="module")
def demo_env(client: TestClient):
    """Patch the demo module to route through the TestClient."""
    from _pytest.monkeypatch import MonkeyPatch
    import importlib

    mp = MonkeyPatch()
    base = str(client.base_url).rstrip("/") + "/api/v2"
    try:
        mp.setattr(demo, "BASE_URL", base)
        mp.setattr(
            demo.DataLayerClient, "call", make_testclient_call(client, base)
        )
        yield
    finally:
        mp.undo()
        importlib.reload(demo)


@pytest.mark.timeout(10)
def test_demo_completes_under_5_seconds(demo_env, caplog):
    """A single demo workflow must complete in < 5 s (#527).

    The ``demo_validate_report`` flow creates actors, submits a report, and
    validates it — exercising several inbox → outbox → delivery cycles.

    Without the conftest fallback patch, each delivery to an unreachable
    host (``vultron.example``) burns ≈ 3.5 s of ``asyncio.sleep`` retries.
    A single demo function hits 4+ deliveries, so baseline is ≈ 14 s.

    With the patch, the fallback adapter is a no-op and the demo completes
    in < 1 s.
    """
    import logging

    start = time.monotonic()
    with caplog.at_level(logging.ERROR):
        demo.main(skip_health_check=True, demos=[demo.demo_validate_report])
    elapsed = time.monotonic() - start

    assert (
        "ERROR SUMMARY" not in caplog.text
    ), f"Demo failed with errors:\n{caplog.text}"
    assert elapsed < 5.0, (
        f"Demo took {elapsed:.1f}s — delivery to unreachable hosts is not"
        f" patched.  Expected < 5 s with the conftest _NullDeliveryAdapter."
    )
