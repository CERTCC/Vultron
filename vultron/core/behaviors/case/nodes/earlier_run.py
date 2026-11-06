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

"""Whether this run is the first to handle the received message (ADR-0154).

:class:`FirstRunOfMessageNode` asks the message's record, never what an
earlier stage of the run left in memory: a stage reads only the record and
the store (ADR-0154).  The refusal stages put it ahead of their effects, so
the re-run of a record a run left in holding does not answer a refusal the
first run may already have answered (CLP-10-044).  The answer is
:func:`~vultron.core.services.received_activity.began_in_an_earlier_run`.
"""

from typing import cast

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers import (
    ACTIVITY_UNAVAILABLE,
    DataLayerConditionWithPorts,
)
from vultron.core.models.events.base import VultronEvent
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.received_activity import began_in_an_earlier_run
from vultron.errors import VultronWiringError

__all__ = ["FirstRunOfMessageNode"]


class FirstRunOfMessageNode(DataLayerConditionWithPorts):
    """Condition: no run before this one began handling the message.

    *intake_ran* says whether the node sits after intake in its tree, which
    decides how the record answers (``began_in_an_earlier_run``).

    Returns:
        SUCCESS when this run is the first to handle the message.

        FAILURE when an earlier run began handling it, and only then: a
        refusal stage reads FAILURE as "skip the refusal effects", so a
        wiring fault must not look like it.

    Raises:
        VultronWiringError: no DataLayer, or no received event on the
            blackboard (ARCH-15-001).  A refusal arm fails toward admit, so
            a fault is raised rather than answered as a re-run.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    def __init__(self, *, intake_ran: bool, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.intake_ran = intake_ran
        self._activity: object | None = None

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self._activity = self._try_get_input("activity")

    def update(self) -> Status:
        event = self._activity
        if self.datalayer is None or not isinstance(event, VultronEvent):
            self.feedback_message = (
                ACTIVITY_UNAVAILABLE
                if self.datalayer is not None
                else "no DataLayer to read the record from"
            )
            raise VultronWiringError(
                f"{self.name}: {self.feedback_message} (got"
                f" {type(event).__name__}; ARCH-15-001)"
            )
        dl = cast(CasePersistence, self.datalayer)
        if began_in_an_earlier_run(
            dl, event.activity_id, intake_ran=self.intake_ran
        ):
            self.feedback_message = (
                f"activity '{event.activity_id}' is the re-run of a record a"
                " run left in holding (ADR-0154)"
            )
            self.logger.debug(
                "%s: %s (actor '%s')",
                self.name,
                self.feedback_message,
                event.actor_id,
            )
            return Status.FAILURE
        return Status.SUCCESS
