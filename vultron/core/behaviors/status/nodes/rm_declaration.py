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

"""Received-side adjudication of an activity-typed RM declaration (RSH-06-006).

An activity such as ``TentativeReject(Offer(VulnerabilityReport))`` or
``Join(VulnerabilityCase)`` declares one RM state for its sender, just as the
``rmState`` of an ``Add(ParticipantStatus)`` does.  The receiver applies one
acceptance rule to both: a forward move is recorded, a non-adjacent one
included; a backward move is refused and the recorded state kept; either
anomaly is logged and flagged for the RSH-06-004 clarification note.

:class:`AdjudicateRMDeclarationNode` is that rule as a precondition guard
(CLP-10-006, CLP-10-009).  It judges the declaration with the helpers the
``Add(ParticipantStatus)`` filter uses —
:func:`~vultron.core.states.rm.classify_rm_declaration` and
:func:`~vultron.core.behaviors.status.nodes.rm_rule.rm_anomaly` — so the
two paths cannot drift apart.

Per specs/received-status-handling.yaml RSH-06-001 to RSH-06-006, RSH-08-001,
RSH-08-002.
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.participant.common import (
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.status.nodes.dimension_filter import (
    BB_RM_ANOMALY,
)
from vultron.core.behaviors.status.nodes.rm_rule import rm_anomaly
from vultron.core.states.rm import (
    RM,
    RMDeclaration,
    classify_rm_declaration,
)

logger = logging.getLogger(__name__)


class AdjudicateRMDeclarationNode(DataLayerConditionWithPorts):
    """Refuse an RM declaration that regresses the sender's recorded state.

    Read-only precondition guard: it reads the sender's participant and writes
    only ``BB_RM_ANOMALY`` to the blackboard, on every tick — ``None`` when the
    declaration is not anomalous — so a previous execution's flag never leaks
    into this one (BT-17-003).

    The subject is the sender, never the executing actor (RSH-08-001): the
    sender's participant is the one whose state is compared.

    Returns:
        SUCCESS when the declaration confirms, advances, or jumps forward
        from the sender's recorded RM state.  :attr:`verdict` records which.

        FAILURE when the declaration is a regression (RSH-06-002), or when the
        case or the sender's participant cannot be found.
    """

    def __init__(
        self,
        sender_actor_id: str,
        declared_rm: RM,
        case_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.sender_actor_id = sender_actor_id
        self.declared_rm = declared_rm
        self.case_id = case_id
        self.verdict: RMDeclaration | None = None

    OUTPUT_PORTS: dict[str, PortInformation] = {
        BB_RM_ANOMALY: PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {BB_RM_ANOMALY: f"/{BB_RM_ANOMALY}"}

    def initialise(self) -> None:
        super().initialise()
        self.verdict = None

    def update(self) -> Status:
        # Clear first: the failure paths below must not inherit a previous
        # execution's anomaly from the process-global blackboard.
        self._set_output(BB_RM_ANOMALY, None)

        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure

        participant_id = case.actor_participant_index.get(self.sender_actor_id)
        if participant_id is None:
            self.feedback_message = (
                f"Sender '{self.sender_actor_id}' has no participant record in"
                f" case '{case.id_}' to record an RM declaration against"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        current_rm, _, _ = resolve_participant_state_from_dl(
            self.datalayer, participant_id
        )
        self.verdict = classify_rm_declaration(current_rm, self.declared_rm)
        anomaly = rm_anomaly(
            current_rm,
            self.declared_rm,
            sender_actor_id=self.sender_actor_id,
            log=self.logger,
            node_name=self.name,
        )
        self._set_output(BB_RM_ANOMALY, anomaly)

        if self.verdict is RMDeclaration.REGRESSION:
            self.feedback_message = (
                f"Refused backward RM declaration {current_rm!r} →"
                f" {self.declared_rm!r} from '{self.sender_actor_id}' in case"
                f" '{case.id_}'; the recorded state stands (RSH-06-002)"
            )
            return Status.FAILURE

        self.logger.debug(
            "%s: RM declaration %s → %s from '%s' is a %s",
            self.name,
            current_rm,
            self.declared_rm,
            self.sender_actor_id,
            self.verdict,
        )
        return Status.SUCCESS
