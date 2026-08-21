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

"""Embargo termination activity emit node (BTND-07-005)."""

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.emit import _SendEmbargoActivityBase
from vultron.core.behaviors.helpers import PortInformation


class SendTerminateEmbargoActivityNode(_SendEmbargoActivityBase):
    """Build and queue a ``Terminate(EmbargoEvent)`` activity.

    Reads ``embargo_id`` and ``case_manager_id`` from the blackboard and
    constructs the outbound activity via ``trigger_activity_factory``.

    Returns FAILURE (BT-14-001) when the factory is unavailable, a required
    blackboard key is missing, or dispatch raises an exception.
    Returns SUCCESS when the activity is created and queued.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(case_id=case_id, name=name)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["embargo_id"] = PortInformation(data_type=str, required=True)
        ports["case_manager_id"] = PortInformation(
            data_type=str, required=True
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "embargo_id": "/embargo_id",
            "case_manager_id": "/case_manager_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.embargo_id: str = self.get_input("embargo_id")
        self.case_manager_id: str = self.get_input("case_manager_id")

    def _on_factory_unavailable(self) -> Status:
        self.feedback_message = (
            "trigger_activity_factory not available"
            " — broadcast FAILURE (BT-14-001)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _resolve_embargo_and_manager(self) -> "tuple[str, str] | Status":
        return self.embargo_id, self.case_manager_id

    def _call_factory(
        self, actor_id: str, embargo_id: str, case_manager_id: str
    ) -> tuple[str, object]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.terminate_embargo(
            embargo_id=embargo_id,
            case_id=self._case_id,
            actor=actor_id,
            to=[case_manager_id],
        )

    def _on_outbox_write_failure(
        self, activity_id: str, exc: Exception
    ) -> Status:
        self.feedback_message = (
            f"Outbox write failed for Terminate(EmbargoEvent)"
            f" '{activity_id}': {exc}"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE
