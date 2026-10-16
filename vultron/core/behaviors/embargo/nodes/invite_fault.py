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

"""The ``Create(ProcessingFault)`` that answers a malformed embargo Invite.

A well-formed activity that breaks a protocol shape rule is received but not
understood, and is answered with ``Create(ProcessingFault)`` (MSM-05-001): an
``Invite(EmbargoEvent)`` that names no embargo, or not exactly one ``to``
recipient (EP-09-010).  The fault id derives from the Invite and the failure
class, so a redelivery emits nothing new (ID-04-004).
"""

from py_trees.common import Status

from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)

__all__ = ["EmitEmbargoInviteFaultNode"]


class EmitEmbargoInviteFaultNode(DataLayerActionWithPorts, EmitCapable):
    """Answer the received Invite's sender with ``Create(ProcessingFault)``.

    Reads the received Invite from ``/activity``; the fault goes to its
    ``actor``, as the executing actor's own act.  Without a trigger-activity
    port nothing can be built: the WARNING says so and the node succeeds, so
    the refusal stands without its fault.  An event naming no id or sender
    has no one to answer and is logged the same way.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def __init__(
        self,
        failure_class: str,
        case_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._failure_class = failure_class
        self._case_id = case_id
        self._activity: object | None = None

    def initialise(self) -> None:
        super().initialise()
        self._activity = self._try_get_input("activity")

    def update(self) -> Status:
        failed_id = getattr(self._activity, "activity_id", None)
        sender_id = getattr(self._activity, "actor_id", None)
        if self.trigger_activity_factory is None or self.actor_id is None:
            self.feedback_message = (
                f"trigger_activity unavailable — ProcessingFault not emitted"
                f" for invite '{failed_id}'"
            )
        elif not failed_id or not sender_id:
            self.feedback_message = (
                "the received Invite names no id or sender — ProcessingFault"
                " not emitted"
            )
        else:
            self.trigger_activity_factory.emit_processing_fault(
                actor=self.actor_id,
                failed_activity_id=failed_id,
                failure_class=self._failure_class,
                to=[sender_id],
                case_id=self._case_id or None,
            )
            self.logger.info(
                "%s: emitted ProcessingFault/%s to '%s' for invite '%s'",
                self.name,
                self._failure_class.rsplit("/", 1)[-1],
                sender_id,
                failed_id,
            )
            return Status.SUCCESS
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS
