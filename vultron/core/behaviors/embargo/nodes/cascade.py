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

"""Embargo persistence BT nodes."""

from py_trees.common import Status

from vultron.core.behaviors.act_keys import EMBARGO
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.errors import VultronAlreadyExistsError


class PersistEmbargoEventNode(DataLayerActionWithPorts):
    """Persist the embargo event the act carries before outbound fan-out.

    The embargo is read from ``/embargo`` (BTND-01-008).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        EMBARGO.name: PortInformation(data_type=EmbargoEvent, required=True),
    }

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {EMBARGO.name: EMBARGO.path}

    def initialise(self) -> None:
        super().initialise()
        self._embargo: EmbargoEvent = self.get_input(EMBARGO.name)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            self.datalayer.create(self._embargo)
        except VultronAlreadyExistsError:
            self.logger.warning(
                "EmbargoEvent '%s' already exists", self._embargo.id_
            )
        return Status.SUCCESS
