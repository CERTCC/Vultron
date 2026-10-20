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

"""RM transition anomaly notification node.

Extracted from ``lifecycle.py`` to keep that module under the 500-line
BTND-07-004 limit.  Re-exported from ``nodes/__init__.py`` so existing import
paths continue to work.

Per specs/received-status-handling.yaml RSH-06-004, RSH-06-005.
"""

import logging

from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.note.case_manager_note import (
    CaseManagerNote,
    _CommitCaseManagerNoteBase,
)
from vultron.core.behaviors.status.nodes.dimension_filter import BB_RM_ANOMALY

logger = logging.getLogger(__name__)


class EmitRMGapNoteNode(_CommitCaseManagerNoteBase):
    """Record the RSH-06-004 note when an RM transition anomaly is detected.

    Reads the ``rm_transition_anomaly`` blackboard key written by
    :class:`~vultron.core.behaviors.status.nodes.dimension_filter.FilterParticipantStatusDimensionsNode`
    (non-adjacent forward jump) or
    :class:`~vultron.core.behaviors.status.nodes.rm_validation.ValidateRMTransitionNode`
    (backward regression on the standalone path).  When the key is ``None``
    (no anomaly), or the tree has no case context, returns SUCCESS without
    doing anything.

    When an anomaly is present, the CASE_MANAGER records a note asking the
    sender to clarify the anomaly as its own ``add_note_to_case`` entry and
    attaches it to the case; the sender learns of it from the ledger
    fan-out, as every active participant does
    (:class:`~vultron.core.behaviors.note.case_manager_note._CommitCaseManagerNoteBase`,
    #4829).  The note is SHOULD-level (RSH-06-004), so a missing
    trigger-activity port or a refused commit is logged and the node
    succeeds; an internal error propagates.

    Per specs/received-status-handling.yaml RSH-06-004, RSH-06-005.
    """

    _BEST_EFFORT = True

    def __init__(
        self,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        # No case context is a no-op (``_compose``), never a commit.
        super().__init__(case_id=case_id or "", name=name)
        self.sender_actor_id = sender_actor_id
        self.case_id = case_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        BB_RM_ANOMALY: PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {BB_RM_ANOMALY: f"/{BB_RM_ANOMALY}"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self.rm_anomaly = self.get_input(BB_RM_ANOMALY)
        except (NoDataAvailable, NotImplementedError):
            self.rm_anomaly = None

    def _compose(self) -> CaseManagerNote | None:
        anomaly = self.rm_anomaly
        if not self.case_id or anomaly is None:
            return None

        anomaly_type = anomaly.get("anomaly_type", "unknown")
        from_rm = anomaly.get("from_rm", "?")
        to_rm = anomaly.get("to_rm", "?")

        if anomaly_type == "gap":
            return CaseManagerNote(
                name=f"RM state gap reported by {self.sender_actor_id}",
                content=(
                    f"Actor '{self.sender_actor_id}' reported a non-adjacent"
                    f" forward RM state jump from {from_rm} to {to_rm}."
                    f" Intermediate transitions were not reported."
                    f" Please clarify the path taken between these states"
                    f" (RSH-06-001)."
                ),
            )
        return CaseManagerNote(
            name=f"RM state regression reported by {self.sender_actor_id}",
            content=(
                f"Actor '{self.sender_actor_id}' reported a backward RM"
                f" state transition from {from_rm} to {to_rm}."
                f" RM is monotonic; this transition was refused (RSH-06-002)."
                f" Please clarify or resync your RM state."
            ),
        )


def rm_gap_note(
    sender_actor_id: str, case_id: str | None
) -> EmitRMGapNoteNode:
    """Return the RSH-06-004 note emitter for the sender's RM declaration.

    The one construction every received RM path uses, whether the note
    follows an accepted gap (an effect) or a refused regression (a refusal
    effect, CLP-10-022).
    """
    return EmitRMGapNoteNode(
        sender_actor_id=sender_actor_id,
        case_id=case_id,
        name="EmitRMGapNote",
    )
