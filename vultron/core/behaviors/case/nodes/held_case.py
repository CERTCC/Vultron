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
"""The held-case door of a received tree (AKM-03-006, ADR-0165).

``Join``, ``Ignore`` and ``Leave`` of a case and the owner's
ownership-transfer proposal, ``Offer(Offer(VulnerabilityCase))``, name their
case and carry none of it (AKM-03-004): the receiver reads every detail from
the case it holds.  A case it does not hold leaves it nothing to act on, so
the act is refused, naming the activity and the case (AKM-03-006).

:class:`CaseNamedByReference` names those acts, and
:class:`ReceiverHoldsNamedCaseNode` is the door that refuses one naming an
unheld case.  ``create_receive_activity_tree`` places it, for a tree that
passes ``held_case``, after the seen-before door and before the path stage:
the path stage would put such a receiver on the no-case path and refuse it
with a reason that names the case but not the activity (HP-01-039), and
AKM-03-006 asks for both.  No tree writes its own copy of the check.
"""

from enum import Enum

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts

__all__ = [
    "CaseNamedByReference",
    "ReceiverHoldsNamedCaseNode",
]


class CaseNamedByReference(Enum):
    """The acts that name their case and carry none of it (AKM-03-004).

    Each member's value is how the act is named in the refusal.
    """

    JOIN = "Join"
    IGNORE = "Ignore"
    LEAVE = "Leave"
    OWNERSHIP_TRANSFER_PROPOSAL = "Offer(Offer)"


class ReceiverHoldsNamedCaseNode(DataLayerConditionWithPorts):
    """Door guard: the receiver holds the case the act names (AKM-03-006).

    Returns:
        SUCCESS when the receiver's store holds *case_id*.

        FAILURE otherwise, with a reason naming the act, the activity and the
        case, logged at WARNING.  Nothing has been recorded: the door runs
        before intake, and the outcome stage leaves the receipt stub
        (CLP-10-010, CLP-10-018).

    A pure read of the store and of the ``/activity`` the bridge placed.

    Args:
        act: Which of the AKM-03-004 acts the tree handles.
        case_id: The case the act names, which the tree is built for.
    """

    def __init__(
        self,
        act: CaseNamedByReference,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.act = act
        self.case_id = case_id
        self._activity: object | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self._activity = self._try_get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        if self._resolve_case_replica(self.case_id) is not None:
            return Status.SUCCESS
        activity_id = getattr(self._activity, "activity_id", None)
        self.feedback_message = (
            f"{self.act.value} '{activity_id}' names unknown case"
            f" '{self.case_id}'"
        )
        self.logger.warning(
            "%s '%s' names case '%s', which this actor does not hold"
            " — REFUSED (AKM-03-006)",
            self.act.value,
            activity_id,
            self.case_id,
        )
        return Status.FAILURE
