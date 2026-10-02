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

"""Case lifecycle trigger nodes for DEMOMA-07-003 steps 4–5.

Contains the auto-close emit node (step 5).  The auto-close precondition and
idempotency guards are in ``conditions.py``; the routing guard is
:class:`~vultron.core.behaviors.sender.nodes.actions.ResolveCaseManagerNode`.

The step-4 embargo teardown (``ThreatTerminationBranchNode``) lives in
:mod:`~vultron.core.behaviors.status.nodes.threat_termination` and is
re-exported from here for backward-compatible import paths.
"""

import logging
from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.status.nodes.threat_termination import (  # noqa: F401
    ThreatTerminationBranchNode,
    _ThreatTerminationSkipConditionNode,
    pxa_embargo_teardown_bt,
    read_pxa_state,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence

logger = logging.getLogger(__name__)


class EmitCloseCaseNode(DataLayerActionWithPorts):
    """Step 5 emit: Queue a ``Leave(VulnerabilityCase)`` to the Case Manager.

    Reads ``case_manager_id`` from the blackboard (written by the preceding
    :class:`~vultron.core.behaviors.sender.nodes.actions.ResolveCaseManagerNode`)
    and calls ``trigger_activity_factory.close_case(...)`` to create and queue
    the activity.

    Returns SUCCESS when the activity is queued successfully or when
    ``trigger_activity_factory`` is absent (best-effort: receive-side paths
    intentionally omit the factory).
    Returns FAILURE only on an unexpected exception during activity creation.

    Per DEMOMA-07-003 step 5, DEMOMA-07-006.
    """

    def __init__(
        self,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_manager_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_manager_id": "/case_manager_id"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self.case_manager_id: str | None = self.get_input(
                "case_manager_id"
            )
        except (NoDataAvailable, NotImplementedError):
            self.case_manager_id = None

    def update(self) -> Status:
        if self.datalayer is None or not self.case_id:
            return Status.SUCCESS

        if self.trigger_activity_factory is None:
            self.logger.warning(
                "EmitCloseCase: no TriggerActivityPort — cannot emit"
                " Leave(VulnerabilityCase) for case '%s'",
                self.case_id,
            )
            return Status.SUCCESS

        case_manager_id = self.case_manager_id
        if not case_manager_id:
            self.feedback_message = (
                f"EmitCloseCase: case_manager_id not set on blackboard"
                f" for case '{self.case_id}' — cannot emit"
            )
            self.logger.warning("%s", self.feedback_message)
            return Status.SUCCESS

        try:
            activity_id, _ = self.trigger_activity_factory.close_case(
                case_id=self.case_id,
                actor=self.actor_id or "",
                to=[case_manager_id],
            )
            cast(CaseOutboxPersistence, self.datalayer).outbox_append(
                activity_id
            )
            self.logger.info(
                "EmitCloseCase: queued Leave(VulnerabilityCase) '%s'"
                " to CaseActor '%s' (DEMOMA-07-003 step 5)",
                activity_id,
                case_manager_id,
            )
        except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
            self.feedback_message = (
                f"EmitCloseCase: failed to emit close_case: {e}"
            )
            self.logger.error("%s", self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE

        return Status.SUCCESS
