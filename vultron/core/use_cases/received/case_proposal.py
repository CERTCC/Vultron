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
from typing import TYPE_CHECKING, Any


from vultron.config.actor import ActorConfig
from vultron.core.behaviors.bridge import BTBridge

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.case_proposal import (
        CaseProposalCallOutBundle,
    )
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.behaviors.case.accept_case_proposal_received_tree import (
    RecordCaseActorAcceptanceNode,
    create_accept_case_proposal_received_tree,
)
from vultron.core.behaviors.case.case_proposal_received_tree import (
    create_case_proposal_received_tree,
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
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    find_node,
    node_succeeded,
    verdict_from_bt,
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
        actor_config: "ActorConfig | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        call_out: "CaseProposalCallOutBundle | None" = None,
    ) -> None:
        self._dl = dl
        self._request: CreateCaseProposalReceivedEvent = request
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
        report from the proposal dict instead.
        """
        raw_report = getattr(
            getattr(activity_obj, "object_", None), "object_", None
        )
        if isinstance(raw_report, VulnerabilityReport):
            return raw_report
        if raw_report is not None:
            logger.warning(
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

        # The vendor who sent Create(as_CaseProposal) is the activity actor.
        vendor_uri = request.actor_id

        # The inner object is the VulnerabilityReport embedded in the proposal.
        report_id = request.inner_object_id

        # receiving_actor_id is the case-actor service URI set by the inbox adapter;
        # falls back to the store's own actor_id on CLI/replay paths (CLP-10-005).
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        # Extract the wire proposal as a plain dict so the Accept can carry it
        # inline (CP-05-003, AKM-03-001). Uses duck-typing to avoid a core→wire
        # import dependency.
        proposal_dict: dict | None = None
        activity_obj = request.activity
        if activity_obj is not None:
            raw_proposal = getattr(activity_obj, "object_", None)
            if raw_proposal is not None and hasattr(
                raw_proposal, "model_dump"
            ):
                # `serialize_as_any=True` is required, not cosmetic: without it
                # Pydantic serialises each field by its *declared* type, so the
                # proposal's inline `object_` — the vulnerability report — is
                # flattened away and the tree receives a proposal with no report
                # to store. Everything derived from the report (the reporter
                # participant, its ledger entry, the SIGNATORY seed) then skips
                # "best-effort" and the reporter never gets a replica. The same
                # flag is needed on the delivery path for the same reason, which
                # `_TestClientRouter.emit` documents.
                #
                # A workaround previously sat here, normalising `target` back to a
                # string because `_rehydrate_fields` had expanded it to a full
                # actor. That expansion was itself the bug and is fixed at source
                # (rehydration now respects the field's declared type), so the
                # workaround is gone.
                #
                # ARCH-20-001 permits this ``by_alias=True``: the subject is a
                # *wire object*, not a core-branch one — ``raw_proposal`` is the
                # inbound activity's own ``object_``, the as_CaseProposal as it
                # arrived. Dumping it reproduces the bytes the vendor sent; it
                # does not synthesise a wire shape for a core object.
                proposal_dict = raw_proposal.model_dump(
                    by_alias=True, serialize_as_any=True
                )

        inline_report = self._core_inline_report(activity_obj, proposal_id)

        tree = create_case_proposal_received_tree(
            report_id=report_id,
            proposal_id=proposal_id,
            vendor_uri=vendor_uri,
            proposal_dict=proposal_dict,
            actor_config=self._actor_config,
            inline_report=inline_report,
            call_out=self._call_out,
        )
        result = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
            trigger_activity=self._trigger_activity,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
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
        from vultron.core.behaviors.case.nodes.proposal_admission_actions import (
            RecordProposalDeclineNode,
        )
        from vultron.core.behaviors.case.nodes.proposal_admission_conditions import (
            CheckDeclineRecordExistsNode,
        )
        from vultron.core.behaviors.case.nodes.proposal_retry_marker import (
            CheckMarkerExistsNode,
        )

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
    """Handle an inbound ``Accept(as_CaseProposal)`` on the vendor actor.

    Updates the vendor's ``VultronReportCaseLink`` with the case-actor URI
    so the subsequent ``Create(VulnerabilityCase)`` bootstrap can validate
    the sender (CP-06-001, CP-06-003).

    BT-15-001 audit: the DataLayer mutation is delegated to a BT leaf node.

    Spec: CP-06-001, CP-06-003.
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: AcceptCaseProposalReceivedEvent,
    ) -> None:
        self._dl = dl
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
        result = BTBridge(datalayer=self._dl).execute_with_setup(
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
    """Handle an inbound ``Reject(as_CaseProposal)`` on the vendor actor.

    Updates the vendor's ``VultronReportCaseLink`` to reflect the rejection,
    setting ``proposal_rejected=True`` and recording any ``rejection_reason``
    present in the activity's ``summary`` field (CP-06-002, CP-06-004).

    BT-15-001 audit: the DataLayer mutation is delegated to a BT leaf node.

    Spec: CP-06-002, CP-06-004.
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: RejectCaseProposalReceivedEvent,
    ) -> None:
        self._dl = dl
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
        result = BTBridge(datalayer=self._dl).execute_with_setup(
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
