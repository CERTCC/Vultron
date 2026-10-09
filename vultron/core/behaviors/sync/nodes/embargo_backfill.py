#!/usr/bin/env python
#
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
"""Backfill participants the embargo gate has just admitted (CM-10-006).

A received activity is committed — and its entry fanned out — *before* its
effect runs (intake → guards → commit → effects, CLP-10-006). So when the effect
is the one that admits a paused participant (it accepts the active embargo, or
the embargo ends), the fan-out of the admitting entry has already withheld it.
This node runs after that effect and sends every admitted peer the entries
withheld from it, the admitting entry included, in log order.

It must run as the CASE_MANAGER, which holds the canonical ledger and the
per-peer pause records; the trees that use it put it behind
``create_case_manager_gated_tree`` (BT-17-001).
"""

from __future__ import annotations

import logging
from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.nodes.embargo_pause import (
    backfill_admitted_peers,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.errors import VultronError, VultronWiringError

logger = logging.getLogger(__name__)


class BackfillAdmittedParticipantsNode(DataLayerActionWithPorts):
    """Send each newly admitted, paused participant what it was not sent.

    Reads ``sync_port``. A missing port is a wiring fault and raises
    ``VultronWiringError``, as the fan-out does (SYNC-02-003, BT-14-001,
    #4126): a silent skip left an admitted peer with no backfill and nothing
    to report it.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._sync_port: SyncActivityPort | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"sync_port": "/sync_port"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self._sync_port = cast(
                SyncActivityPort, self.get_input("sync_port")
            )
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_obj, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure

        if self._sync_port is None:
            raise VultronWiringError(
                f"{self.name}: sync_port must be injected to backfill the"
                f" peers admitted on case '{self.case_id}' (SYNC-02-003)"
            )

        try:
            backfilled = backfill_admitted_peers(
                cast(CasePersistence, self.datalayer),
                case_obj,
                sync_port=self._sync_port,
                actor_id=self.actor_id,
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.exception("%s: embargo gate undecidable", self.name)
            return Status.FAILURE
        self.feedback_message = (
            f"backfilled {len(backfilled)} admitted participant(s)"
        )
        return Status.SUCCESS
