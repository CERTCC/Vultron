"""Received-side use cases for the CaseProposal protocol.

Three use cases covering the full CP message flow (ADR-0023):

- ``CreateCaseProposalReceivedUseCase`` — case-actor service receives
  ``Create(as_CaseProposal)`` from a report receiver; creates a VulnerabilityCase
  and emits ``Accept(as_CaseProposal)`` + ``Create(VulnerabilityCase)``
  (CP-05-001 through CP-05-004).

- ``AcceptCaseProposalReceivedUseCase`` — report receiver receives
  ``Accept(as_CaseProposal)`` from the case-actor service; records the
  case-actor URI in the receiver's VultronReportCaseLink (CP-06-001,
  CP-06-003).

- ``RejectCaseProposalReceivedUseCase`` — report receiver receives
  ``Reject(as_CaseProposal)`` from the case-actor service; logs the
  rejection so the receiver can surface it (CP-06-002, CP-06-004).
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
from typing import TYPE_CHECKING, Any

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import WIRE_RENDER_PORT_UNAVAILABLE
from vultron.errors import VultronWiringError

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.case_proposal import (
        CaseProposalCallOutBundle,
    )
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.behaviors.case.accept_case_proposal_received_tree import (
    RecordCaseActorAcceptanceNode,
    create_accept_case_proposal_received_tree,
)
from vultron.core.behaviors.case.case_proposal_received_tree import (
    create_case_proposal_received_tree,
)
from vultron.core.behaviors.case.nodes.proposal_admission_actions import (
    RecordProposalDeclineNode,
)
from vultron.core.behaviors.case.nodes.proposal_admission_conditions import (
    CheckDeclineRecordExistsNode,
)
from vultron.core.behaviors.case.nodes.proposal_retry_marker import (
    CheckMarkerExistsNode,
)
from vultron.core.behaviors.case.reject_case_proposal_received_tree import (
    RecordCaseProposalRejectionNode,
    create_reject_case_proposal_received_tree,
)
from vultron.core.models.events.case_proposal import (
    AcceptCaseProposalReceivedEvent,
    CreateCaseProposalReceivedEvent,
    RejectCaseProposalReceivedEvent,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    find_node,
    node_succeeded,
    verdict_from_bt,
)
from vultron.core.use_cases.received._sender_embargo_proposal import (
    sender_embargo_proposal_inputs,
)

logger = logging.getLogger(__name__)


def _skipped_if_no_link(
    tree: Any,
    node_type: (
        type[RecordCaseActorAcceptanceNode]
        | type[RecordCaseProposalRejectionNode]
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


class CreateCaseProposalReceivedUseCase:
    """Handle an inbound ``Create(as_CaseProposal)`` on the case-actor service.

    Delegates to ``CreateCaseProposalReceivedBT``, which creates a
    VulnerabilityCase and emits two outbound activities:

    1. ``Accept(as_CaseProposal)`` — acknowledgement to the report receiver
    2. ``Create(VulnerabilityCase)`` — case announcement to the report receiver

    BT-15-001 audit: all DataLayer mutations and outbox enqueues are
    delegated to leaf nodes of the BT tree.

    Spec: CP-05-001 through CP-05-004.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: CreateCaseProposalReceivedEvent,
        actor_config: "ActorConfig | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        call_out: "CaseProposalCallOutBundle | None" = None,
        sync_port: "SyncActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: CreateCaseProposalReceivedEvent = request
        # The native ledger commits (CommitNativeLedgerEntriesNode) fan each
        # entry out through this port.  It is injected explicitly so the
        # fan-out is part of the use case's declared contract — and so a test
        # can observe the outbox order it produces (CM-14-011, CP-05-003)
        # rather than inheriting whatever port a previous execution left on
        # the blackboard (BT-17-007 restores it, so normally: none).
        self._sync_port = sync_port
        # CFG-07-002/CFG-07-004: the CVD roles the proposing actor receives
        # alongside CVDRole.CASE_OWNER come from the local actor config, not a
        # hard-coded assumption that every report receiver is a vendor.
        self._actor_config = actor_config
        self._wire_render_port = wire_render_port
        # Needed only on the decline path: _EmitRejectCaseProposalNode builds
        # Reject(as_CaseProposal) through the shared emit seam (CP-05-004,
        # OX-14-001).  The accept path does not use it.
        self._trigger_activity = trigger_activity
        # Admission policy (CP-05-002).  The adapter chooses the bundle, the
        # same way it chooses STATUS_AUTHORIZATION_PERMISSIVE for the received-
        # side status gates: a deployment with an admission policy injects its
        # own here rather than editing the tree.  `None` means the core
        # DETERMINISTIC default, which admits (BT-23-001, BT-23-011).
        self._call_out = call_out

    @staticmethod
    def _core_inline_report(
        activity_obj: Any, proposal_id: str
    ) -> VulnerabilityReport | None:
        """Return the proposal's inline report, if the proposal carries one.

        Under ADR-0099 detail 3 the report the wire parser validated *is* the
        core ``VulnerabilityReport`` — ``as_VulnerabilityReport`` is an alias
        of that class — so there is no projection step and none is duck-typed
        (ARCH-20-008).  Anything else in the slot (a bare IRI the parser could
        not dereference, or a foreign object) is not a report the tree can
        seed from; ``None`` tells ``StoreProposalReportNode`` to rebuild the
        report from the proposal dict instead, and that node owns the WARNING
        when the rebuild has nothing to work with.
        """
        raw_report = getattr(
            getattr(activity_obj, "object_", None), "object_", None
        )
        if isinstance(raw_report, VulnerabilityReport):
            return raw_report
        if raw_report is not None:
            # ``StoreProposalReportNode._report_from_proposal_dict`` warns on
            # the same condition with the CP-01-004 remedy, so keep this at
            # DEBUG rather than doubling the WARNING.
            logger.debug(
                "create_case_proposal_received: proposal '%s' carries a %s"
                " where an inline report was expected — falling back to the"
                " proposal dict",
                proposal_id,
                type(raw_report).__name__,
            )
        return None

    def execute(self) -> HandlerResult:
        request = self._request
        proposal_id = request.proposal_id
        if proposal_id is None:
            logger.warning(
                "create_case_proposal_received: no proposal_id — refusing"
            )
            return HandlerResult.refused(
                "Create(CaseProposal) carries no proposal id"
            )

        # The report receiver who sent Create(as_CaseProposal) is the activity
        # actor, and becomes the CASE_OWNER.
        owner_uri = request.actor_id

        # The inner object is the VulnerabilityReport embedded in the proposal.
        report_id = request.inner_object_id

        # receiving_actor_id is the case-actor service URI set by the inbox adapter;
        # falls back to the store's own actor_id on CLI/replay paths (CLP-10-005).
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        # Render the proposal as a plain AS2 dict so the Accept can carry it
        # inline (CP-05-003, AKM-03-001).  The subject handed to the port is the
        # core-branch ``VultronActivity`` the extractor built; its ``object`` is
        # the as_CaseProposal as it arrived.  Core renders nothing itself
        # (ARCH-20-001): the port is the only route to the AS2 shape, so a
        # proposal cannot be handled without it.  A missing port is this
        # actor's composition fault, never the sender's, so it raises rather
        # than refusing the proposal (#2255, ADR-0095).
        #
        # The render keeps the proposal's inline ``object_`` — the vulnerability
        # report — because ``VultronActivity.object_`` is typed ``Any`` and so is
        # serialised by its runtime type.  Losing it would give the tree a
        # proposal with no report to store, and everything derived from the
        # report (the reporter participant, its ledger entry, the SIGNATORY
        # seed) would silently skip, so the reporter would never get a replica.
        proposal_dict: dict | None = None
        activity_obj = request.activity
        if activity_obj is not None and hasattr(
            getattr(activity_obj, "object_", None), "model_dump"
        ):
            if self._wire_render_port is None:
                raise VultronWiringError(WIRE_RENDER_PORT_UNAVAILABLE)
            rendered = self._wire_render_port.render(activity_obj).get(
                "object"
            )
            if isinstance(rendered, dict):
                proposal_dict = rendered

        inline_report = self._core_inline_report(activity_obj, proposal_id)

        tree = create_case_proposal_received_tree(
            report_id=report_id,
            proposal_id=proposal_id,
            owner_uri=owner_uri,
            proposal_dict=proposal_dict,
            actor_config=self._actor_config,
            inline_report=inline_report,
            call_out=self._call_out,
        )
        result = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
            # The proposer's inline profile is the only source of the
            # CASE_OWNER's actor default (CP-01-010).
            owner_profile=request.proposer_profile,
            **sender_embargo_proposal_inputs(request),
        )
        verdict = verdict_from_bt(
            tree, result, label="CreateCaseProposalReceivedBT"
        )
        if verdict.disposition is HandlerDisposition.APPLIED:
            verdict = self._classify_success(tree, proposal_id)
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "create_case_proposal_received: refused proposal '%s': %s",
                proposal_id,
                verdict.reason,
            )
        elif verdict.disposition is HandlerDisposition.APPLIED:
            logger.info(
                "create_case_proposal_received: case created and responses"
                " queued for proposal '%s'",
                proposal_id,
            )
        return verdict

    @staticmethod
    def _classify_success(tree: Any, proposal_id: str) -> HandlerResult:
        """Say which arm of the idempotency Selector answered (#2255).

        The tree succeeds on all four arms, but only the accept arm applied
        the proposal.  A Selector leaves the arms it tried ahead of the winner
        FAILED and the ones after it INVALID, so the first guard that
        succeeded names the arm.
        """
        if node_succeeded(tree, CheckMarkerExistsNode):
            # CP-05-005: Accept already sent; the retry runner owns the Create.
            return HandlerResult.skipped(
                f"proposal '{proposal_id}' already accepted; Create in flight"
            )
        if node_succeeded(tree, CheckDeclineRecordExistsNode):
            # HP-01-003: a pre-existing decline record is a duplicate — the
            # earlier REFUSED is the record; replaying the same message is a
            # benign no-op, not a new refusal.
            return HandlerResult.skipped(
                f"proposal '{proposal_id}' was previously declined"
            )
        if node_succeeded(tree, RecordProposalDeclineNode):
            # CP-05-002, CP-05-004: the admission policy said no.
            return HandlerResult.refused(
                f"proposal '{proposal_id}' declined by admission policy"
            )
        return HandlerResult.applied()


class AcceptCaseProposalReceivedUseCase:
    """Handle an inbound ``Accept(as_CaseProposal)`` on the report receiver.

    Updates the receiver's ``VultronReportCaseLink`` with the case-actor URI
    so the subsequent ``Create(VulnerabilityCase)`` bootstrap can validate
    the sender (CP-06-001, CP-06-003).

    BT-15-001 audit: the DataLayer mutation is delegated to a BT leaf node.

    Spec: CP-06-001, CP-06-003.
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: AcceptCaseProposalReceivedEvent,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
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
        )
        result = BTBridge(
            datalayer=self._dl, wire_render_port=self._wire_render_port
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
    """Handle an inbound ``Reject(as_CaseProposal)`` on the report receiver.

    Updates the receiver's ``VultronReportCaseLink`` to reflect the rejection,
    setting ``proposal_rejected=True`` and recording any ``rejection_reason``
    present in the activity's ``summary`` field (CP-06-002, CP-06-004).

    BT-15-001 audit: the DataLayer mutation is delegated to a BT leaf node.

    Spec: CP-06-002, CP-06-004.
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: RejectCaseProposalReceivedEvent,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
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
            rejection_reason=rejection_reason,
        )
        result = BTBridge(
            datalayer=self._dl, wire_render_port=self._wire_render_port
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
