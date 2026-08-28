#!/usr/bin/env python
"""
Info endpoint for the Vultron API (D5-1-G1).

Returns the configured ``VULTRON_SERVER__BASE_URL`` and the list of actor IDs
this node hosts so that demo scripts and operators can confirm container
identity at startup.  The list comes from ``hosted_actor_ids()``, not from
scanning a shared DataLayer — there is no unscoped store to scan (ADR-0073).

References: specs/multi-actor-demo.yaml DEMOMA-02-001,
notes/multi-actor-architecture.md §4 G1.
"""

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

from fastapi import APIRouter

from vultron.adapters.driven import actor_hosts
from vultron.adapters.utils import BASE_URL

router = APIRouter(tags=["Info"])


@router.get("/info", operation_id="info_get")
def get_info() -> dict:
    """Returns server identity information (D5-1-G1).

    Response includes the configured ``VULTRON_SERVER__BASE_URL`` and the actors
    this node **hosts**.  Useful for demo scripts and operators to confirm which
    container they are talking to at startup.

    Before ADR-0073 this scanned the shared DataLayer for every actor-typed row,
    which also returned the container's *peers* — actors it merely knew an
    address for.  Peers are not hosted here, so they are no longer listed.
    """
    return {"base_url": BASE_URL, "actors": actor_hosts.hosted_actor_ids()}
