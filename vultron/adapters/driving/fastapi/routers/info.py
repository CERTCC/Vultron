#!/usr/bin/env python
"""
Info endpoint for the Vultron API (D5-1-G1).

Returns this node's base URL (the configured ``VULTRON_SERVER__BASE_URL``
unless the serving app declares its own) and the list of actor IDs this node
hosts so that demo scripts and operators can confirm container identity at
startup.  The list comes from ``hosted_actor_ids()``, not from
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

from fastapi import APIRouter, Request

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driving.fastapi.deps import (
    node_base_url,
    node_db_url_template,
)
from vultron.config import get_config

router = APIRouter(tags=["Info"])


@router.get("/info", operation_id="info_get")
def get_info(request: Request) -> dict:
    """Returns server identity information (D5-1-G1).

    Response includes this node's base URL and the actors this node **hosts**.
    Useful for demo scripts and operators to confirm which container they are
    talking to at startup.

    Both are the serving app's own (``deps.node_base_url``,
    ``deps.node_db_url_template``) when it declares them, so each of several
    nodes in one process reports itself and lists only its own actors
    (DL-07-011, DL-07-012).  An app that declares neither reports the
    configured ``VULTRON_SERVER__BASE_URL`` and enumerates the configured
    storage, which is the deployment case.

    Before ADR-0073 this scanned the shared DataLayer for every actor-typed row,
    which also returned the container's *peers* — actors it merely knew an
    address for.  Peers are not hosted here, so they are no longer listed.
    """
    declared_base = node_base_url(request)
    base_url = (
        declared_base
        if declared_base is not None
        else get_config().server.base_url
    )
    return {
        "base_url": base_url,
        "actors": actor_hosts.hosted_actor_ids(
            node_db_url_template(request), base_url
        ),
    }
