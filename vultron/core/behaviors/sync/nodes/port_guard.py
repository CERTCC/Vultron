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

"""Guard that a ledger commit can be fanned out before it is minted."""

from __future__ import annotations

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.errors import VultronWiringError


class RequireSyncPortNode(DataLayerActionWithPorts):
    """Raise ``VultronWiringError`` unless ``/sync_port`` is on the blackboard.

    The canonical store announces every entry it commits to every active
    participant (SYNC-02-003), so a commit without the port is a wiring fault.
    The fan-out node raises on a missing port too, but by then the entry is
    already persisted, so the ledger would keep an entry that no replica
    receives and whose effect the outer tree never applies. This node runs
    first in the mint sequence and refuses before anything is written
    (BT-14-001, #4113).

    It sits after ``DeclineForeignLedgerCommitNode``. A store that declines
    mints nothing and fans out nothing, so it needs no port.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"sync_port": "/sync_port"}

    def update(self) -> Status:
        try:
            port = self.get_input("sync_port")
        except (NoDataAvailable, NotImplementedError):
            port = None
        if port is None:
            raise VultronWiringError(
                f"{self.name}: sync_port must be injected before a ledger"
                " entry is committed, so the entry can be fanned out"
                " (SYNC-02-003)"
            )
        return Status.SUCCESS


__all__ = ["RequireSyncPortNode"]
