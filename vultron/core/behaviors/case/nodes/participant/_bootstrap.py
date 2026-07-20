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

"""Bootstrap participant BT node.

Separated from participant_add.py to keep that module under the BTND-07-004
500-line limit.  This node is only used during Create(VulnerabilityCase)
bootstrap flows, not during normal report-receive flows.
"""

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.participant.common import (
    _ensure_reporter_participant,
)
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.report_case_link import VultronReportCaseLink


class EnsureReporterParticipantAtAcceptedNode(DataLayerAction):
    """BT leaf node that seeds or upgrades the reporter participant to RM.ACCEPTED.

    Called from ``CreateCaseReceivedUseCase._handle_bootstrap`` via BTBridge
    after a ``Create(VulnerabilityCase)`` bootstrap.  When participants arrive
    as bare string IDs, ``_store_embedded_participants`` cannot create records
    for them.  This node ensures the reporter's participant record exists at
    ``RM.ACCEPTED`` — inferred from the fact that they submitted a report (#589,
    #624).

    Args:
        link: The ``VultronReportCaseLink`` associating the report to the case.
        case_obj: The bootstrapped ``VulnerabilityCase`` domain object.
        case_id: ID of the case (for log context).
    """

    def __init__(
        self,
        link: VultronReportCaseLink,
        case_obj: VulnerabilityCase,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.link = link
        self.case_obj = case_obj
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        _ensure_reporter_participant(
            self.datalayer,
            self.link,
            self.case_obj,
            self.case_id,
        )
        return Status.SUCCESS
