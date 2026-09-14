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

"""Integration test: delivery failure → requeue path (ISSUE-1877).

Exercises OX-05-002: remote delivery failures SHOULD be logged at WARNING
level and retried.
"""

import asyncio

import pytest

from test.demo.conftest import (
    _TestClientRouter,
    create_isolated_actor_app,
)
from vultron.adapters.driving.fastapi.outbox_handler import (
    configure_default_emitter,
    get_default_emitter,
    outbox_handler,
)

#: Vendor and finder base URLs for this test module — must be unique across
#: all demo tests to avoid cross-contaminating the named in-memory stores.
_VENDOR_BASE = "http://vendor-requeue.test"
_FINDER_BASE = "http://finder-requeue.test"


@pytest.mark.spec("OX-05-002")
def test_delivery_failure_triggers_requeue():
    """Failed outbox delivery requeues the activity for retry (OX-05-002).

    Steps:
      1. Create two isolated actors (vendor and finder) with their own
         in-memory stores.
      2. Inject a simulated delivery failure for the finder's base URL.
      3. Submit a report from vendor addressed to finder — this queues an
         ``Offer(VulnerabilityReport)`` in the vendor's outbox and drains it
         via a synchronous background task.  The injected failure fires
         repeatedly until the per-pass error cap (> 3) is reached and the
         drain aborts, leaving the activity in the outbox.
      4. Assert the activity ID is present in the vendor's outbox.
      5. Clear the injected failure and drain again — delivery succeeds and
         the outbox is empty.
    """
    router = _TestClientRouter()
    vendor_iso = create_isolated_actor_app(_VENDOR_BASE, router, "vendor")
    finder_iso = create_isolated_actor_app(_FINDER_BASE, router, "finder")

    with vendor_iso.client, finder_iso.client:
        vendor_actor_id = vendor_iso.actor_id
        finder_actor_id = finder_iso.actor_id

        # Create both actors in their respective stores.
        r = vendor_iso.client.post(
            "/api/v2/actors/",
            json={
                "type": "Organization",
                "name": "Vendor",
                "id": vendor_actor_id,
            },
        )
        assert r.status_code in (200, 201), f"vendor create: {r.text}"

        r = finder_iso.client.post(
            "/api/v2/actors/",
            json={
                "type": "Organization",
                "name": "Finder",
                "id": finder_actor_id,
            },
        )
        assert r.status_code in (200, 201), f"finder create: {r.text}"

        prev_emitter = get_default_emitter()
        configure_default_emitter(router)  # type: ignore[arg-type]
        try:
            # Inject a persistent delivery failure for the finder's base URL.
            # Unlike a one-shot failure, this fires on every emit attempt
            # until explicitly cleared.  The outbox_handler loop will keep
            # requeuing the activity and fail the same item more than 3 times,
            # at which point the per-pass cap (OX-13-006) stops the drain and
            # leaves the activity in the outbox.
            router.inject_failure(_FINDER_BASE)

            # Submit a report from vendor to finder.  The trigger endpoint
            # queues an Offer(VulnerabilityReport) and schedules
            # outbox_handler as a background task.  TestClient runs
            # background tasks synchronously, so this drain — which aborts
            # after the per-pass error cap — completes before this call
            # returns.
            resp = vendor_iso.client.post(
                "/api/v2/actors/vendor/trigger/submit-report",
                json={
                    "report_name": "Test Vulnerability",
                    "report_content": "Details of a test vulnerability.",
                    "recipient_id": finder_actor_id,
                },
            )
            assert (
                resp.status_code == 202
            ), f"submit-report failed: {resp.text}"

            # The drain aborted after repeated DeliveryErrors; the activity
            # must still be in the outbox (OX-05-002: requeued for retry).
            pending = vendor_iso.dl.outbox_list()
            assert len(pending) == 1, (
                f"Expected 1 requeued activity after failed delivery, "
                f"got {len(pending)}: {pending}"
            )

            # Clear the injected failure so the next drain can succeed.
            router._failing_hosts.discard(_FINDER_BASE)

            # Drain again — delivery to finder now succeeds.
            asyncio.run(outbox_handler(vendor_actor_id, vendor_iso.dl))

            # Outbox must be empty after successful retry delivery.
            assert vendor_iso.dl.outbox_list() == [], (
                f"Expected empty outbox after successful retry, "
                f"got: {vendor_iso.dl.outbox_list()}"
            )
        finally:
            configure_default_emitter(prev_emitter)  # type: ignore[arg-type]
