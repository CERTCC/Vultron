"""BT tree for the AcceptCaseProposal received-side use case.

Vendor side: handles an inbound ``Accept(as_CaseProposal)`` by recording
the case-actor URI in the vendor's ``VultronReportCaseLink``, making it
available for the subsequent ``Create(VulnerabilityCase)`` bootstrap.

Spec: ``specs/case-proposal.yaml`` CP-06-001, CP-06-003.
"""

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

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.report_case_link import VultronReportCaseLink

logger = logging.getLogger(__name__)


class _RecordCaseActorAcceptanceNode(DataLayerAction):
    """Update the vendor's VultronReportCaseLink with the case-actor URI.

    When the case-actor service accepts the proposal, the vendor records
    the case-actor URI as ``trusted_case_actor_id`` so the subsequent
    ``Create(VulnerabilityCase)`` bootstrap can validate the sender
    (CP-06-003, CBT-01-006).

    Returns SUCCESS even when no matching link is found, because the vendor
    may not always have submitted a report offer before the proposal flow
    (e.g. relay scenarios).  Missing-link situations are logged at WARNING.
    """

    def __init__(
        self,
        report_id: str,
        case_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id
        self._case_actor_id = case_actor_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        link_id = VultronReportCaseLink.build_id(self._report_id)
        link = self.datalayer.read(link_id)

        if not isinstance(link, VultronReportCaseLink):
            logger.warning(
                "%s: No VultronReportCaseLink found for report '%s'"
                " — cannot record case-actor URI (CP-06-003)",
                self.name,
                self._report_id,
            )
            return Status.SUCCESS

        link.trusted_case_actor_id = self._case_actor_id
        self.datalayer.save(link)
        logger.info(
            "%s: Recorded case-actor URI '%s' for report '%s' (CP-06-003)",
            self.name,
            self._case_actor_id,
            self._report_id,
        )
        return Status.SUCCESS


def create_accept_case_proposal_received_tree(
    report_id: str,
    case_actor_id: str,
) -> py_trees.behaviour.Behaviour:
    """Return the received-side BT for processing ``Accept(as_CaseProposal)``.

    Records the case-actor URI in the vendor's ``VultronReportCaseLink``
    so the subsequent ``Create(VulnerabilityCase)`` bootstrap step can
    validate the sender (CP-06-003, CBT-01-006).

    Args:
        report_id: URI of the VulnerabilityReport linked to the proposal.
        case_actor_id: URI of the case-actor service that accepted the
            proposal (the ``actor`` of the inbound ``Accept`` activity).

    Returns:
        A py_trees Sequence behaviour ready for ``BTBridge.execute_with_setup``.
    """
    return py_trees.composites.Sequence(
        name="AcceptCaseProposalReceivedBT",
        memory=False,
        children=[
            _RecordCaseActorAcceptanceNode(
                report_id=report_id,
                case_actor_id=case_actor_id,
            ),
        ],
    )
