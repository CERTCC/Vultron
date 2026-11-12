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

"""Received use case for ``Create(CaseProposal)`` at the case-actor service.

The service creates a VulnerabilityCase from the proposal and emits
``Accept(CaseProposal)`` and ``Create(VulnerabilityCase)`` (ADR-0023,
CP-05-001 through CP-05-004).
"""

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.case_proposal_received_tree import (
    create_case_proposal_received_tree,
)
from vultron.core.behaviors.case.nodes.proposal_admission_actions import (
    RecordProposalDeclineNode,
)
from vultron.core.behaviors.case.nodes.proposal_admission_conditions import (
    CheckDeclineRecordExistsNode,
    CheckProposalCaseFullyClosedNode,
)
from vultron.core.behaviors.helpers import WIRE_RENDER_PORT_UNAVAILABLE
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.case_proposal import (
    CreateCaseProposalReceivedEvent,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.services.report_case_inputs import StatedReportFields
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    find_node,
    node_succeeded,
    verdict_from_bt,
)
from vultron.core.use_cases.received._sender_embargo_proposal import (
    sender_embargo_proposal_inputs,
)
from vultron.errors import VultronWiringError

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.case_proposal import (
        CaseProposalCallOutBundle,
    )
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)


def _stated_report_fields(
    request: CreateCaseProposalReceivedEvent,
    inline_report: VulnerabilityReport | None,
    sender_terms: dict[str, Any],
) -> StatedReportFields:
    """What the carried Offer and its report state, which a CSAF value never beats.

    The name and summary are the carried Offer's report's (CP-01-008), else
    the proposal's own report's, which is the same report: a case starts
    with its report's name and summary (CSAF-03-006).  The proposed
    embargo end is that of the Offer's ``proposedEmbargo`` only when it is
    still terms for this report (*sender_terms*, from
    :func:`sender_embargo_proposal_inputs`): a proposal already run out, or
    about another subject, is read as no proposal, so it neither shapes the
    case nor sets a CSAF disclosure date aside (CSAF-02-003, CSAF-03-001).
    """
    name = request.offered_report_name
    summary = request.offered_report_summary
    if inline_report is not None:
        name = name or inline_report.name
        summary = summary or inline_report.summary
    proposal = sender_terms.get("sender_proposed_embargo")
    return StatedReportFields(
        name=name,
        summary=summary,
        proposed_embargo_end=(
            proposal.end_time if isinstance(proposal, EmbargoEvent) else None
        ),
    )


class CreateCaseProposalReceivedUseCase:
    """Handle an inbound ``Create(CaseProposal)`` on the case-actor service.

    Delegates to ``CreateCaseProposalReceivedBT``, which creates a
    VulnerabilityCase and emits two outbound activities:

    1. ``Accept(CaseProposal)`` — acknowledgement to the report receiver
    2. ``Create(VulnerabilityCase)`` — case announcement to the report receiver

    BT-15-001 audit: all DataLayer mutations and outbox enqueues are
    delegated to leaf nodes of the BT tree.

    A proposal that resolves to a fully closed case is declined with
    ``Reject(CaseProposal)`` and reported ``REFUSED`` (CP-05-014,
    CP-05-018, CM-23-013).

    Spec: CP-05-001 through CP-05-004, CP-05-006, CP-05-008, CP-05-010.
    """

    # The proposal precedes the case, so the rule is for an actor outside
    # any case.  Its author is the proposer this CASE_MANAGER recorded for the
    # proposal id; an id it has not recorded is a new proposal, which any
    # actor may make, the admission decision being the call-out point's
    # (CP-05-002).  The proposal id is the sender's choice, so another
    # proposer's admitted or declined id is refused (CP-05-010, #4719).
    sender_entitlement: ClassVar[SenderRule] = SenderRule.before_case(
        SenderEntitlementKind.AUTHOR
    )

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: CreateCaseProposalReceivedEvent,
        actor_config: ActorConfig | None = None,
        wire_render_port: WireRenderPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
        call_out: CaseProposalCallOutBundle | None = None,
        sync_port: SyncActivityPort | None = None,
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
        # The CaseActor's own configuration (its protocol default embargo,
        # EP-04-005).  The proposer's CVD roles are not in it: they ride on the
        # proposal (CP-09-007, ADR-0133).
        self._actor_config = actor_config
        self._wire_render_port = wire_render_port
        # Needed only on the decline path: _EmitRejectCaseProposalNode builds
        # Reject(CaseProposal) through the shared emit seam (CP-05-004,
        # OX-14-001).  The accept path does not use it.
        self._trigger_activity = trigger_activity
        # Admission policy (CP-05-002).  The adapter chooses the bundle, the
        # same way it chooses STATUS_AUTHORIZATION_PERMISSIVE for the received-
        # side status adoption gate: a deployment with an admission policy injects its
        # own here rather than editing the tree.  `None` means the core
        # DETERMINISTIC default, which admits (BT-23-001, BT-23-011).
        self._call_out = call_out

    @staticmethod
    def _core_inline_report(
        activity_obj: Any, proposal_id: str | None
    ) -> VulnerabilityReport | None:
        """Return the proposal's inline report, if the proposal carries one.

        Under ARCH-25-003 (ADR-0099) the report the wire parser validated *is* the
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
        # A proposal with no id is refused by the tree itself (CLP-10-005).
        proposal_id = request.proposal_id

        # The report receiver who sent Create(CaseProposal) is the activity
        # actor, and becomes the CASE_OWNER if the proposal is admitted.
        proposer_uri = request.actor_id

        # The inner object is the VulnerabilityReport embedded in the proposal.
        report_id = request.inner_object_id

        # receiving_actor_id is the case-actor service URI set by the inbox adapter;
        # falls back to the store's own actor_id on CLI/replay paths (CLP-10-005).
        receiving_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        # Render the proposal as a plain AS2 dict so the Accept can carry it
        # inline (CP-05-003, CP-05-009).  The subject handed to the port is the
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
        # report (the reporter participant, its ledger entry, the signatory
        # seed) would silently skip, so the reporter would never get a replica.
        proposal_dict: dict | None = None
        activity_obj = request.activity
        # A proposal with no id never reaches a node that reads the
        # rendering: its tree only archives and refuses it.
        if (
            proposal_id is not None
            and activity_obj is not None
            and hasattr(getattr(activity_obj, "object_", None), "model_dump")
        ):
            if self._wire_render_port is None:
                raise VultronWiringError(WIRE_RENDER_PORT_UNAVAILABLE)
            rendered = self._wire_render_port.render(activity_obj).get(
                "object"
            )
            if isinstance(rendered, dict):
                proposal_dict = rendered

        inline_report = self._core_inline_report(activity_obj, proposal_id)
        # A proposal with no id is refused in-tree, so its terms are never
        # read (CLP-10-018).
        sender_terms = (
            sender_embargo_proposal_inputs(request)
            if proposal_id is not None
            else {}
        )

        tree = create_case_proposal_received_tree(
            report_id=report_id,
            proposal_id=proposal_id,
            proposer_uri=proposer_uri,
            proposal_dict=proposal_dict,
            actor_config=self._actor_config,
            inline_report=inline_report,
            call_out=self._call_out,
            proposer_case_roles=request.proposer_case_roles,
            sender_rule=self.sender_entitlement,
            claims_readings=request.claims_readings,
            stated_report_fields=_stated_report_fields(
                request, inline_report, sender_terms
            ),
            activity_id=request.activity_id,
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
            **sender_terms,
        )
        verdict = verdict_from_bt(
            tree, result, label="CreateCaseProposalReceivedBT"
        )
        if (
            verdict.disposition is HandlerDisposition.APPLIED
            and proposal_id is not None
        ):
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
        if node_succeeded(tree, CheckDeclineRecordExistsNode):
            # HP-01-003: a pre-existing decline record is a duplicate — the
            # earlier REFUSED is the record; replaying the same message is a
            # benign no-op, not a new refusal.
            return HandlerResult.skipped(
                f"proposal '{proposal_id}' was previously declined"
            )
        closed = find_node(tree, CheckProposalCaseFullyClosedNode)
        if closed is not None and closed.closed_case_id is not None:
            # CP-05-014, CP-05-018: the proposal's case is fully closed, so the
            # CASE_MANAGER declined it and wrote nothing for the case
            # (CM-23-013).
            return HandlerResult.refused(
                f"proposal '{proposal_id}' resolves to case"
                f" '{closed.closed_case_id}', which is fully closed (CM-23-013)"
            )
        if node_succeeded(tree, RecordProposalDeclineNode):
            # CP-05-002, CP-05-004: the admission policy said no.
            return HandlerResult.refused(
                f"proposal '{proposal_id}' declined by admission policy"
            )
        return HandlerResult.applied()
