#!/usr/bin/env python
"""
Info endpoint for the Vultron API (D5-1-G1).

Returns the configured ``VULTRON_BASE_URL`` and the list of actor IDs
registered in the shared DataLayer so that demo scripts and operators
can confirm container identity at startup.

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

from fastapi import APIRouter, Depends

from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.utils import BASE_URL
from vultron.core.ports.datalayer import DataLayer

router = APIRouter(tags=["Info"])

_ACTOR_TABLE_NAMES = [
    "Actor",
    "Application",
    "Group",
    "Organization",
    "Person",
    "Service",
]


def _shared_dl() -> DataLayer:
    """Dependency: always returns the shared (non-actor-scoped) DataLayer."""
    return get_datalayer()


@router.get("/info", operation_id="info_get")
def get_info(dl: DataLayer = Depends(_shared_dl)) -> dict:
    """Returns server identity information (D5-1-G1).

    Response includes the configured ``VULTRON_BASE_URL`` and the list of
    actor IDs registered in this container's shared DataLayer.  Useful
    for demo scripts and operators to confirm which container they are
    talking to at startup.
    """
    actor_ids: list[str] = []
    for table in _ACTOR_TABLE_NAMES:
        for rec in dl.get_all(table):
            actor_id = rec.get("id_")
            if actor_id:
                actor_ids.append(actor_id)

    return {"base_url": BASE_URL, "actors": actor_ids}
