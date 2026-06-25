"""BT tree for the RejectCaseProposal received-side use case.

Vendor side: handles an inbound ``Reject(as_CaseProposal)`` by recording
the rejection state in the vendor's ``VultronReportCaseLink``.

Spec: ``specs/case-proposal.yaml`` CP-06-002, CP-06-004.
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


class _RecordCaseProposalRejectionNode(DataLayerAction):
    """Mark the vendor's VultronReportCaseLink as rejected.

    When the case-actor service rejects the proposal, the vendor records
    ``proposal_rejected=True`` and, when provided, the ``rejection_reason``
    so it can be surfaced to the operator (CP-06-004).

    Returns SUCCESS even when no matching link is found, because the vendor
    may not always have submitted a report offer before the proposal flow
    (e.g. relay scenarios).  Missing-link situations are logged at WARNING.
    """

    def __init__(
        self,
        report_id: str,
        rejection_reason: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id
        self._rejection_reason = rejection_reason

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
                " — cannot record rejection state (CP-06-004)",
                self.name,
                self._report_id,
            )
            return Status.SUCCESS

        link.proposal_rejected = True
        link.rejection_reason = self._rejection_reason or None
        self.datalayer.save(link)
        logger.info(
            "%s: Recorded proposal rejection for report '%s'"
            " (reason: %r) (CP-06-004)",
            self.name,
            self._report_id,
            self._rejection_reason,
        )
        return Status.SUCCESS


def create_reject_case_proposal_received_tree(
    report_id: str,
    rejection_reason: str | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the received-side BT for processing ``Reject(as_CaseProposal)``.

    Marks the vendor's ``VultronReportCaseLink`` as rejected and records
    the rejection reason when present, allowing the vendor to surface the
    rejection to the operator (CP-06-002, CP-06-004).

    Args:
        report_id: URI of the VulnerabilityReport linked to the proposal.
        rejection_reason: Human-readable reason from the case-actor service,
            taken from the Reject activity's ``summary`` field.  ``None``
            when not provided.

    Returns:
        A py_trees Sequence behaviour ready for ``BTBridge.execute_with_setup``.
    """
    return py_trees.composites.Sequence(
        name="RejectCaseProposalReceivedBT",
        memory=False,
        children=[
            _RecordCaseProposalRejectionNode(
                report_id=report_id,
                rejection_reason=rejection_reason,
            ),
        ],
    )
