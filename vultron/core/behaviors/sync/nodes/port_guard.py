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

"""Guards that a ledger commit can be rendered and fanned out before it is minted."""

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

    ``/sync_port`` is written by :class:`~vultron.core.behaviors.bridge.BTBridge`
    from its ``sync_port`` constructor argument, rebound to the executing
    store (BT-05-005); a nested bridge inherits it from the outer tree's
    blackboard. The port is read in ``initialise()`` (BTND-03-011) and is
    declared optional so its absence surfaces as this wiring error rather
    than as ``NoDataAvailable``.

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

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sync_port: object | None = None

    def initialise(self) -> None:
        super().initialise()
        try:
            self._sync_port = self.get_input("sync_port")
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None

    def update(self) -> Status:
        if self._sync_port is None:
            raise VultronWiringError(
                f"{self.name}: sync_port must be injected before a ledger"
                " entry is committed, so the entry can be fanned out"
                " (SYNC-02-003)"
            )
        return Status.SUCCESS


class RequireWireRenderPortNode(DataLayerActionWithPorts):
    """Raise ``VultronWiringError`` unless the tree has a ``wire_render_port``.

    A ledger snapshot is the AS2 rendering of the record it carries, and core
    never produces that shape itself (ARCH-20-001).  A tree that writes records
    and then commits their entries places this ahead of its first write, so a
    composition fault refuses before anything is stored instead of leaving
    records no entry describes (CLP-07-013, #4440).
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def update(self) -> Status:
        self._require_wire_render_port()
        return Status.SUCCESS


__all__ = ["RequireSyncPortNode", "RequireWireRenderPortNode"]
