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

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.embargo_event import EmbargoEvent


class PersistEmbargoEventNode(DataLayerAction):
    """Persist the trigger-created embargo event before outbound fan-out."""

    def __init__(self, embargo: EmbargoEvent, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._embargo = embargo

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE
        try:
            self.datalayer.create(self._embargo)
        except ValueError:
            self.logger.warning(
                "EmbargoEvent '%s' already exists", self._embargo.id_
            )
        return Status.SUCCESS
