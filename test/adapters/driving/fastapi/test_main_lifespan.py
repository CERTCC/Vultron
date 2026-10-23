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

"""The served (root) application runs the OutboxMonitor safety-net drain.

``vultron.adapters.driving.fastapi.main:app`` is what uvicorn serves in every
container.  Starlette does not propagate lifespan events to a mounted
sub-application, so the process-level startup ``app_v2``'s lifespan performs
has to happen in the root lifespan too.  A hand-maintained copy of that list
omitted the ``OutboxMonitor``: no container ever ran the OX-09-002 safety-net
poll, and an activity queued in an outbox that no inline drain happened to be
looping over waited for the next inbound activity to that actor — 111 s for an
ownership-transfer Offer in CI run 36643399281 (#3602, ADR-0112).  The root
lifespan now shares ``_make_lifespan`` with ``app_v2``, so the two cannot
drift apart again.
"""

from fastapi.testclient import TestClient

from vultron.adapters.driving.fastapi.main import app
from vultron.adapters.driving.fastapi.outbox_monitor import OutboxMonitor


def test_root_lifespan_starts_the_outbox_monitor_and_stops_it_on_shutdown():
    with TestClient(app):
        monitor = getattr(app.state, "outbox_monitor", None)
        assert isinstance(monitor, OutboxMonitor), (
            "the served app must run the OutboxMonitor safety-net drain"
            " (OX-09-002); main.py's root lifespan did not start one"
        )
        task = monitor._task
        assert task is not None and not task.done()
    assert getattr(app.state, "outbox_monitor", None) is None
