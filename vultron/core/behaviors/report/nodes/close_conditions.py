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

"""Report-closure guard nodes for the report behavior tree.

Split from ``conditions`` to keep that leaf under the BTND-07-004 line cap.
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.rm import RM, is_valid_rm_transition


class CheckReportClosable(DataLayerConditionWithPorts):
    """Check that the report's RM state may move to ``RM.CLOSED``.

    Returns SUCCESS when the report's ``ReportCaseLink`` is at ``RM.CLOSED``
    already (a repeat close is a status confirmation) or at a state the RM
    transition function closes from (*Received*, *Invalid*, *Accepted*,
    *Deferred* — RMB-14-004).  Returns FAILURE when the link is missing or the
    report is at a state with no close edge, which is *Valid* (VP-02-004).

    Runs ahead of the close emit, so a closure the RM table refuses is refused
    before any ``Reject`` is sent: a ``Reject`` sent from RM *Received* **is**
    the ``R → C`` transition (RMB-14-004), and none may be sent for a
    transition that is not recorded.  The write node keeps its own check
    (``TransitionRMtoClosed``); this guard only orders the refusal first.
    """

    def __init__(self, report_id: str, name: str | None = None) -> None:
        """Initialize CheckReportClosable.

        Args:
            report_id: ID of the VulnerabilityReport to check.
            name: Optional custom node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        """Succeed when ``RM.CLOSED`` is reachable from the report's RM state.

        Returns:
            SUCCESS when the report is closed or closable; FAILURE when the
            DataLayer is unavailable, the link is missing, or the RM table has
            no close edge from the report's state.
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        link = self.datalayer.read(
            VultronReportCaseLink.build_id(self.report_id)
        )
        if not isinstance(link, VultronReportCaseLink):
            self.feedback_message = (
                f"ReportCaseLink not found for report '{self.report_id}'"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        current_rm = link.rm_state
        if current_rm != RM.CLOSED and not is_valid_rm_transition(
            current_rm, RM.CLOSED
        ):
            self.feedback_message = (
                f"Report '{self.report_id}' cannot close from RM"
                f" {current_rm.name}: the RM transition function has no"
                f" {current_rm.name} -> CLOSED edge (RMB-14-004, VP-02-004)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.logger.debug(
            "%s: report '%s' may close from RM %s",
            self.name,
            self.report_id,
            current_rm.name,
        )
        return Status.SUCCESS
