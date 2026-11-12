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

"""Received use cases for the case-actor service's answer to a CaseProposal.

The report receiver records the case-actor URI on its
VultronReportCaseLink for an ``Accept(CaseProposal)`` (CP-06-001,
CP-06-003) and logs a ``Reject(CaseProposal)`` (CP-06-002, CP-06-004).
"""

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.accept_case_proposal_received_tree import (
    RecordCaseActorAcceptanceNode,
    create_accept_case_proposal_received_tree,
)
from vultron.core.behaviors.case.reject_case_proposal_received_tree import (
    RecordCaseProposalRejectionNode,
    create_reject_case_proposal_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.events.case_proposal import (
    AcceptCaseProposalReceivedEvent,
    RejectCaseProposalReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    find_node,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)


def _skipped_if_no_link(
    tree: Any,
    node_type: (
        type[RecordCaseActorAcceptanceNode | RecordCaseProposalRejectionNode]
    ),
    report_id: str,
) -> HandlerResult:
    """``SKIPPED`` when there was no report link to record the answer on.

    The tree succeeds either way; with no link (a relay, or a proposal this
    actor never made) nothing changed (#2255).
    """
    node = find_node(tree, node_type)
    if node is not None and not node.link_found:
        return HandlerResult.skipped(
            f"no VultronReportCaseLink for report '{report_id}'"
        )
    return HandlerResult.applied()


class AcceptCaseProposalReceivedUseCase:
    """Handle an inbound ``Accept(CaseProposal)`` on the report receiver.

    Updates the receiver's ``VultronReportCaseLink`` with the case-actor URI
    so the subsequent ``Create(VulnerabilityCase)`` bootstrap can validate
    the sender (CP-06-001, CP-06-003).

    BT-15-001 audit: the DataLayer mutation is delegated to a BT leaf node.

    Spec: CP-06-001, CP-06-003.
    """

    # The sender must be the actor the vendor addressed the proposal to,
    # as recorded on the report case link (CP-06-005).  The proposal
    # precedes the case, so the rule is for an actor outside any case.
    sender_entitlement: ClassVar[SenderRule] = SenderRule.before_case(
        SenderEntitlementKind.NAMED_ACTOR
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: AcceptCaseProposalReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: AcceptCaseProposalReceivedEvent = request

    def execute(self) -> HandlerResult:
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
            return HandlerResult.refused(
                "Accept(CaseProposal) carries no inline report"
            )

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        tree = create_accept_case_proposal_received_tree(
            report_id=report_id,
            case_actor_id=case_actor_id,
            sender_rule=self.sender_entitlement,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        verdict = verdict_from_bt(
            tree, result, label="AcceptCaseProposalReceivedBT"
        )
        if verdict.disposition is HandlerDisposition.APPLIED:
            verdict = _skipped_if_no_link(
                tree, RecordCaseActorAcceptanceNode, report_id
            )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "accept_case_proposal_received: refused for report '%s': %s",
                report_id,
                verdict.reason,
            )
        elif verdict.disposition is HandlerDisposition.APPLIED:
            logger.info(
                "accept_case_proposal_received: recorded case-actor '%s'"
                " for report '%s'",
                case_actor_id,
                report_id,
            )
        return verdict


class RejectCaseProposalReceivedUseCase:
    """Handle an inbound ``Reject(CaseProposal)`` on the report receiver.

    Updates the receiver's ``VultronReportCaseLink`` to reflect the rejection,
    setting ``proposal_rejected=True`` and recording any ``rejection_reason``
    present in the activity's ``summary`` field (CP-06-002, CP-06-004).

    BT-15-001 audit: the DataLayer mutation is delegated to a BT leaf node.

    Spec: CP-06-002, CP-06-004.
    """

    # As for the Accept: the addressee of the proposal (CP-06-005).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.before_case(
        SenderEntitlementKind.NAMED_ACTOR
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: RejectCaseProposalReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request: RejectCaseProposalReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request

        # The inner object is the VulnerabilityReport embedded in the proposal.
        report_id = request.inner_object_id
        if report_id is None:
            logger.warning(
                "reject_case_proposal_received: no report_id available"
                " — cannot update VultronReportCaseLink (CP-06-004)"
            )
            return HandlerResult.refused(
                "Reject(CaseProposal) carries no inline report"
            )

        # The rejection reason comes from the Reject activity's summary field.
        rejection_reason: str | None = None
        if request.activity is not None:
            rejection_reason = request.activity.summary

        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        tree = create_reject_case_proposal_received_tree(
            report_id=report_id,
            sender_actor_id=request.actor_id,
            rejection_reason=rejection_reason,
            sender_rule=self.sender_entitlement,
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        verdict = verdict_from_bt(
            tree, result, label="RejectCaseProposalReceivedBT"
        )
        if verdict.disposition is HandlerDisposition.APPLIED:
            verdict = _skipped_if_no_link(
                tree, RecordCaseProposalRejectionNode, report_id
            )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "reject_case_proposal_received: refused for report '%s': %s",
                report_id,
                verdict.reason,
            )
        elif verdict.disposition is HandlerDisposition.APPLIED:
            logger.info(
                "reject_case_proposal_received: case-actor '%s' rejected"
                " proposal for report '%s' (reason: %r) (CP-06-004)",
                request.actor_id,
                report_id,
                rejection_reason,
            )
        return verdict
