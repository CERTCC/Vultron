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

from py_trees.common import Status

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.bridge import BTBridge

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.behaviors.case.accept_case_proposal_received_tree import (
    create_accept_case_proposal_received_tree,
)
from vultron.core.behaviors.case.case_proposal_received_tree import (
    create_case_proposal_received_tree,
)
from vultron.core.behaviors.case.reject_case_proposal_received_tree import (
    create_reject_case_proposal_received_tree,
)
from vultron.core.models.events.case_proposal import (
    AcceptCaseProposalReceivedEvent,
    CreateCaseProposalReceivedEvent,
    RejectCaseProposalReceivedEvent,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)

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
        actor_config: "ActorConfig | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: CreateCaseProposalReceivedEvent = request
        # CFG-07-002/CFG-07-004: the CVD roles the proposing actor receives
        # alongside CVDRole.CASE_OWNER come from the local actor config, not a
        # hard-coded assumption that every report receiver is a vendor.
        self._actor_config = actor_config
        self._wire_render_port = wire_render_port

    @staticmethod
    def _core_inline_report(
        activity_obj: Any, proposal_id: str
    ) -> VulnerabilityReport | None:
        """Return the proposal's inline report in its core shape, if present.

        The proposal dict handed to the tree is deliberately wire-spelled — the
        ``Accept`` must carry the proposal inline on the wire (CP-05-003,
        AKM-03-001) — and that is exactly why the report cannot be rebuilt from
        it: ``by_alias=True`` writes the reporter as ``attributedTo``, while the
        core ``VulnerabilityReport`` declares ``attributed_to`` and sets
        ``extra="ignore"``. Validating that dict dropped the reporter without
        complaint, the report stored fine, and the three things derived from it —
        the reporter participant, its ledger entry, the SIGNATORY seed — each
        skipped "best-effort" (#2482).

        Mapping the spellings is the wire layer's own job, via ``to_core()``.
        Duck-typed for the same reason ``model_dump`` is at the call site: core
        MUST NOT import wire (ARCH-03-001).
        """
        raw_report = getattr(
            getattr(activity_obj, "object_", None), "object_", None
        )
        to_core = getattr(raw_report, "to_core", None)
        if not callable(to_core):
            return None
        try:
            candidate = to_core()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "create_case_proposal_received: could not convert the inline"
                " report of proposal '%s' to its core shape: %s — falling back"
                " to the proposal dict",
                proposal_id,
                exc,
            )
            return None
        return (
            candidate if isinstance(candidate, VulnerabilityReport) else None
        )

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
        )
        result = BTBridge(
            datalayer=self._dl,
            wire_render_port=self._wire_render_port,
        ).execute_with_setup(
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
        dl: CasePersistence,
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

    def execute(self) -> None:
        request = self._request

        # The inner object is the VulnerabilityReport embedded in the proposal.
        report_id = request.inner_object_id
        if report_id is None:
            logger.warning(
                "reject_case_proposal_received: no report_id available"
                " — cannot update VultronReportCaseLink (CP-06-004)"
            )
            return

        # The rejection reason comes from the Reject activity's summary field.
        rejection_reason: str | None = None
        if request.activity is not None:
            rejection_reason = request.activity.summary

        receiving_actor_id = request.receiving_actor_id or request.actor_id

        tree = create_reject_case_proposal_received_tree(
            report_id=report_id,
            rejection_reason=rejection_reason,
        )
        result = BTBridge(datalayer=self._dl).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            logger.warning(
                "reject_case_proposal_received: BT did not succeed"
                " for report '%s': %s",
                report_id,
                BTBridge.get_failure_reason(tree) or result.feedback_message,
            )
        else:
            logger.info(
                "reject_case_proposal_received: case-actor '%s' rejected"
                " proposal for report '%s' (reason: %r) (CP-06-004)",
                request.actor_id,
                report_id,
                rejection_reason,
            )
