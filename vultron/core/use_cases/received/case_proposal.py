"""Received-side use cases for the CaseProposal protocol.

Three use cases covering the full CP message flow (ADR-0023):

- ``CreateCaseProposalReceivedUseCase`` — case-actor service receives
  ``Create(as_CaseProposal)`` from a vendor; creates a VulnerabilityCase
  and emits ``Accept(as_CaseProposal)`` + ``Create(VulnerabilityCase)``
  (CP-05-001 through CP-05-004).

- ``AcceptCaseProposalReceivedUseCase`` — vendor receives
  ``Accept(as_CaseProposal)`` from the case-actor service; records the
  case-actor URI in the vendor's VultronReportCaseLink (CP-06-001,
  CP-06-003).

- ``RejectCaseProposalReceivedUseCase`` — vendor receives
  ``Reject(as_CaseProposal)`` from the case-actor service; logs the
  rejection so the vendor can surface it (CP-06-002, CP-06-004).
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

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.accept_case_proposal_received_tree import (
    create_accept_case_proposal_received_tree,
)
from vultron.core.behaviors.case.case_proposal_received_tree import (
    create_case_proposal_received_tree,
)
from vultron.core.models.events.case_proposal import (
    AcceptCaseProposalReceivedEvent,
    CreateCaseProposalReceivedEvent,
    RejectCaseProposalReceivedEvent,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


class CreateCaseProposalReceivedUseCase:
    """Handle an inbound ``Create(as_CaseProposal)`` on the case-actor service.

    Delegates to ``CreateCaseProposalReceivedBT``, which creates a
    VulnerabilityCase and emits two outbound activities:

    1. ``Accept(as_CaseProposal)`` — acknowledgement to the vendor
    2. ``Create(VulnerabilityCase)`` — case announcement to the vendor

    BT-15-001 audit: all DataLayer mutations and outbox enqueues are
    delegated to leaf nodes of the BT tree.

    Spec: CP-05-001 through CP-05-004.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: CreateCaseProposalReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: CreateCaseProposalReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        proposal_id = request.proposal_id
        if proposal_id is None:
            logger.warning(
                "create_case_proposal_received: no proposal_id — skipping"
            )
            return

        # The vendor who sent Create(as_CaseProposal) is the activity actor.
        vendor_uri = request.actor_id

        # The inner object is the VulnerabilityReport embedded in the proposal.
        report_id = request.inner_object_id

        # receiving_actor_id is the case-actor service URI set by the inbox adapter.
        receiving_actor_id = request.receiving_actor_id
        if receiving_actor_id is None:
            logger.warning(
                "create_case_proposal_received: no receiving_actor_id"
                " — skipping (CLP-10-005)"
            )
            return

        # Extract the wire proposal as a plain dict so the Accept can carry it
        # inline (CP-05-003, MV-09-001). Uses duck-typing to avoid a core→wire
        # import dependency.
        proposal_dict: dict | None = None
        activity_obj = request.activity
        if activity_obj is not None:
            raw_proposal = getattr(activity_obj, "object_", None)
            if raw_proposal is not None and hasattr(
                raw_proposal, "model_dump"
            ):
                proposal_dict = raw_proposal.model_dump(by_alias=True)

        tree = create_case_proposal_received_tree(
            report_id=report_id,
            proposal_id=proposal_id,
            vendor_uri=vendor_uri,
            proposal_dict=proposal_dict,
        )
        result = BTBridge(datalayer=self._dl).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            logger.warning(
                "create_case_proposal_received: BT did not fully succeed"
                " for proposal '%s': %s",
                proposal_id,
                BTBridge.get_failure_reason(tree) or result.feedback_message,
            )
        else:
            logger.info(
                "create_case_proposal_received: case created and responses"
                " queued for proposal '%s'",
                proposal_id,
            )


class AcceptCaseProposalReceivedUseCase:
    """Handle an inbound ``Accept(as_CaseProposal)`` on the vendor actor.

    Updates the vendor's ``VultronReportCaseLink`` with the case-actor URI
    so the subsequent ``Create(VulnerabilityCase)`` bootstrap can validate
    the sender (CP-06-001, CP-06-003).

    BT-15-001 audit: the DataLayer mutation is delegated to a BT leaf node.

    Spec: CP-06-001, CP-06-003.
    """

    def __init__(
        self,
        dl: DataLayer,
        request: AcceptCaseProposalReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: AcceptCaseProposalReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        # The case-actor service that accepted the proposal is the activity actor.
        case_actor_id = request.actor_id

        # The inner object is the VulnerabilityReport embedded in the proposal.
        report_id = request.inner_object_id
        if report_id is None:
            logger.warning(
                "accept_case_proposal_received: no report_id available"
                " — cannot update VultronReportCaseLink (CP-06-003)"
            )
            return

        receiving_actor_id = request.receiving_actor_id or request.actor_id

        tree = create_accept_case_proposal_received_tree(
            report_id=report_id,
            case_actor_id=case_actor_id,
        )
        result = BTBridge(datalayer=self._dl).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            logger.warning(
                "accept_case_proposal_received: BT did not succeed"
                " for report '%s': %s",
                report_id,
                BTBridge.get_failure_reason(tree) or result.feedback_message,
            )
        else:
            logger.info(
                "accept_case_proposal_received: recorded case-actor '%s'"
                " for report '%s'",
                case_actor_id,
                report_id,
            )


class RejectCaseProposalReceivedUseCase:
    """Handle an inbound ``Reject(as_CaseProposal)`` on the vendor actor.

    Logs the rejection so the vendor can surface it and take corrective
    action (CP-06-002, CP-06-004).

    TODO(#1088): CP-06-004 MUST — update vendor local state to reflect
    rejection (e.g., mark VultronReportCaseLink as rejected with rejection
    reason when present). A BT tree delegating via BTBridge is required once
    this state field exists.

    Spec: CP-06-002, CP-06-004.
    """

    def __init__(
        self,
        dl: DataLayer,
        request: RejectCaseProposalReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RejectCaseProposalReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.warning(
            "reject_case_proposal_received: case-actor '%s' rejected"
            " proposal '%s' (CP-06-004)",
            request.actor_id,
            request.proposal_id,
        )
