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

"""
Demo-only trigger router.

Exposes endpoints used exclusively by demo scripts to puppeteer actors through
steps their own BTs would handle autonomously in a real deployment.

This router is conditionally mounted only when
``get_config().mode == RunMode.PROTOTYPE`` (TRIG-09-002).
In ``RunMode.PROD`` these paths are simply not registered, so any request to
``/actors/{id}/demo/`` returns HTTP 404 (TRIG-09-003).

Every trigger here is a thin wrapper: it validates the HTTP body, builds the
verb's core request and hands it to
:func:`~vultron.adapters.driving.fastapi.trigger_runner.run_trigger`.

The routes are grouped by concern (CS-18-005): ``actions`` holds the
puppeteering POSTs and ``ledger`` the ledger reads.

Spec: TRIG-08-004, TRIG-09-001 through TRIG-09-005, TRIG-10-003, TRIG-10-004.
"""

from fastapi import APIRouter

from vultron.adapters.driving.fastapi.routers.demo_triggers import (
    actions,
    ledger,
)
from vultron.adapters.driving.fastapi.routers.demo_triggers.actions import (
    demo_add_note_to_case,
    demo_notify_fix_deployed,
    demo_notify_fix_ready,
    demo_notify_published,
    demo_set_stub_summary,
    demo_sync_log_entry,
)
from vultron.adapters.driving.fastapi.routers.demo_triggers.ledger import (
    demo_get_case_ledger,
    demo_get_case_ledger_entry,
    demo_stream_case_ledger,
)

# Each submodule's router carries the ``/actors`` prefix and the tag itself,
# so every route keeps the path and tags it was declared with.
router = APIRouter()
router.include_router(actions.router)
router.include_router(ledger.router)

__all__ = [
    "demo_add_note_to_case",
    "demo_get_case_ledger",
    "demo_get_case_ledger_entry",
    "demo_notify_fix_deployed",
    "demo_notify_fix_ready",
    "demo_notify_published",
    "demo_set_stub_summary",
    "demo_stream_case_ledger",
    "demo_sync_log_entry",
    "router",
]
