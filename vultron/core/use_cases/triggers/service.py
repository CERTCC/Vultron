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

"""Facade over all actor-initiated trigger use cases.

:class:`TriggerService` is the concrete implementation of
:class:`~vultron.core.ports.trigger_service.TriggerServicePort`.  It accepts
a :class:`~vultron.core.ports.case_persistence.CaseOutboxPersistence` at
construction and exposes all 18 trigger operations as named methods.  ``SqliteDataLayer``
satisfies this protocol structurally.

Callers (FastAPI routers, CLI adapters, domain tests) construct a
``TriggerService`` directly::

    svc = TriggerService(dl)
    result = svc.propose_embargo(actor_id=..., case_id=..., end_time=...)
    result.activity  # an ActivityResult; every method returns its verb's
                     # TriggerResult subtype (UCORG-05-005, ADR-0110)

Domain errors bubble up as bare ``VultronError`` subclasses; the HTTP adapter
layer translates them via ``domain_error_translation()``.

No HTTP framework imports permitted in this module.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from vultron.enums.roles import CVDRole
from vultron.core.models.use_case_result import (
    ActivityResult,
    CaseResult,
    NoteResult,
    OfferResult,
    RoleOfferResult,
    StatusResult,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers.actor import (
    SvcAcceptActorRecommendationUseCase,
    SvcAcceptCaseInviteUseCase,
    SvcAcceptCaseOwnershipTransferUseCase,
    SvcInviteActorToCaseUseCase,
    SvcOfferCaseOwnershipTransferUseCase,
    SvcOfferCaseParticipantRoleUseCase,
    SvcRejectCaseInviteUseCase,
    SvcSuggestActorToCaseUseCase,
)
from vultron.core.use_cases.triggers.case import (
    SvcAddObjectToCaseUseCase,
    SvcAddParticipantStatusUseCase,
    SvcAddReportToCaseUseCase,
    SvcCreateCaseUseCase,
    SvcDeferCaseUseCase,
    SvcEngageCaseUseCase,
    SvcLeaveCaseUseCase,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoRevisionUseCase,
    SvcProposeEmbargoUseCase,
    SvcRejectEmbargoUseCase,
    SvcTerminateEmbargoUseCase,
)
from vultron.core.use_cases.triggers.note import SvcAddNoteToCaseUseCase
from vultron.core.use_cases.triggers.report import (
    SvcCloseCaseUseCase,
    SvcInvalidateReportUseCase,
    SvcRejectReportUseCase,
    SvcSubmitReportUseCase,
    SvcValidateReportUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptActorRecommendationTriggerRequest,
    AcceptCaseInviteTriggerRequest,
    AcceptCaseOwnershipTransferTriggerRequest,
    AcceptEmbargoTriggerRequest,
    AddNoteToCaseTriggerRequest,
    AddObjectToCaseTriggerRequest,
    AddParticipantStatusTriggerRequest,
    AddReportToCaseTriggerRequest,
    CloseReportTriggerRequest,
    CreateCaseTriggerRequest,
    DeferCaseTriggerRequest,
    EngageCaseTriggerRequest,
    LeaveCaseTriggerRequest,
    InvalidateReportTriggerRequest,
    InviteActorToCaseTriggerRequest,
    OfferCaseOwnershipTransferTriggerRequest,
    OfferCaseParticipantRoleTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
    RejectCaseInviteTriggerRequest,
    RejectEmbargoTriggerRequest,
    RejectReportTriggerRequest,
    SubmitReportTriggerRequest,
    SuggestActorToCaseTriggerRequest,
    TerminateEmbargoTriggerRequest,
    ValidateReportTriggerRequest,
)
from vultron.core.ports.sync_activity import SyncActivityPort

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort


class TriggerService:
    """Facade over all actor-initiated trigger use cases.

    Accepts a :class:`~vultron.core.ports.case_persistence.CaseOutboxPersistence`
    at construction; exposes every trigger operation as a named method.  Hides
    the 18 ``SvcXxx`` use-case class names, the ``XxxTriggerRequest``
    hierarchy, and the ``(dl, request).execute()`` dispatch protocol from
    callers.

    ``SqliteDataLayer`` (and any
    :class:`~vultron.core.ports.datalayer.DataLayer`) satisfies
    ``CaseOutboxPersistence`` structurally.

    Raises bare ``VultronError`` subclasses — HTTP adapters translate these
    via ``domain_error_translation()``.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port

    def _bt_ports(self) -> dict[str, Any]:
        """The driven ports every BT-backed trigger use case is built with.

        One place, so a port every trigger tree needs — the
        ``WireRenderPort`` its ledger commits render through (ARCH-20-001) —
        cannot be forgotten at one of the call sites below.
        """
        return {
            "trigger_activity": self._trigger_activity,
            "wire_render_port": self._wire_render_port,
        }

    # -----------------------------------------------------------------------
    # Report triggers
    # -----------------------------------------------------------------------

    def submit_report(
        self,
        actor_id: str,
        report_name: str,
        report_content: str,
        recipient_id: str,
    ) -> OfferResult:
        """Create a VulnerabilityReport and offer it to *recipient_id*."""
        req = SubmitReportTriggerRequest(
            actor_id=actor_id,
            report_name=report_name,
            report_content=report_content,
            recipient_id=recipient_id,
        )
        return SvcSubmitReportUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def validate_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> ActivityResult:
        """Validate a received report offer, transitioning RM state."""
        req = ValidateReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note
        )
        return SvcValidateReportUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def invalidate_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> ActivityResult:
        """Mark a received report offer as invalid."""
        req = InvalidateReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note
        )
        return SvcInvalidateReportUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def reject_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> ActivityResult:
        """Hard-close a report offer before validation completes."""
        req = RejectReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note or None
        )
        return SvcRejectReportUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def close_case(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> ActivityResult:
        """Close a VulnerabilityCase via the RM lifecycle (Case Owner only)."""
        req = CloseReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note
        )
        return SvcCloseCaseUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def close_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> ActivityResult:
        """Deprecated alias for :meth:`close_case`."""
        return self.close_case(actor_id, offer_id, note)

    # -----------------------------------------------------------------------
    # Case triggers
    # -----------------------------------------------------------------------

    def create_case(
        self,
        actor_id: str,
        name: str,
        content: str,
        report_id: str | None = None,
        to: list[str] | None = None,
    ) -> CaseResult:
        """Create a local VulnerabilityCase and queue it for the CaseActor."""
        req = CreateCaseTriggerRequest(
            actor_id=actor_id,
            name=name,
            content=content,
            report_id=report_id,
            to=to,
        )
        return SvcCreateCaseUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def engage_case(
        self,
        actor_id: str,
        case_id: str,
    ) -> ActivityResult:
        """Accept a case, transitioning RM state to ACCEPTED."""
        req = EngageCaseTriggerRequest(actor_id=actor_id, case_id=case_id)
        return SvcEngageCaseUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def defer_case(
        self,
        actor_id: str,
        case_id: str,
    ) -> ActivityResult:
        """Defer a case, transitioning RM state to DEFERRED."""
        req = DeferCaseTriggerRequest(actor_id=actor_id, case_id=case_id)
        return SvcDeferCaseUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def leave_case(
        self,
        actor_id: str,
        case_id: str,
    ) -> ActivityResult:
        """Send Leave(VulnerabilityCase) to the Case Actor (ADR-0050).

        Routes ``Leave(VulnerabilityCase)`` to the Case Actor inbox so the
        Case Actor can commit a ``close_case`` ledger entry and broadcast it
        to all participants.  The receiver-side role semantics (owner closes
        all, non-owner departs only) are applied on the Case Actor replica.
        """
        req = LeaveCaseTriggerRequest(actor_id=actor_id, case_id=case_id)
        return SvcLeaveCaseUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def add_report_to_case(
        self,
        actor_id: str,
        case_id: str,
        report_id: str,
    ) -> ActivityResult:
        """Link a VulnerabilityReport to an existing VulnerabilityCase."""
        req = AddReportToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            report_id=report_id,
        )
        return SvcAddReportToCaseUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def add_object_to_case(
        self,
        actor_id: str,
        case_id: str,
        object_id: str,
    ) -> ActivityResult:
        """Add any existing AS2 object to a case (TRIG-10-001)."""
        req = AddObjectToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            object_id=object_id,
        )
        return SvcAddObjectToCaseUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def add_note_to_case(
        self,
        actor_id: str,
        case_id: str,
        note_name: str,
        note_content: str,
        in_reply_to: str | None = None,
    ) -> NoteResult:
        """Create a Note and add it to a case."""
        req = AddNoteToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            note_name=note_name,
            note_content=note_content,
            in_reply_to=in_reply_to,
        )
        return SvcAddNoteToCaseUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def add_participant_status(
        self,
        actor_id: str,
        case_id: str,
        rm_state: RM | None = None,
        vf_state: CS_vf | None = None,
        d_state: CS_d | None = None,
        pxa_state: CS_pxa | None = None,
    ) -> StatusResult:
        """Self-report actor RM/VF/D/PXA state to the Case Manager (DEMOMA-07-001)."""
        req = AddParticipantStatusTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            rm_state=rm_state,
            vf_state=vf_state,
            d_state=d_state,
            pxa_state=pxa_state,
        )
        return SvcAddParticipantStatusUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    # -----------------------------------------------------------------------
    # Embargo triggers
    # -----------------------------------------------------------------------

    def propose_embargo(
        self,
        actor_id: str,
        case_id: str,
        end_time: datetime,
        note: str | None = None,
    ) -> ActivityResult:
        """Propose a new embargo or revision to an active embargo."""
        req = ProposeEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            end_time=end_time,
            note=note,
        )
        return SvcProposeEmbargoUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def accept_embargo(
        self,
        actor_id: str,
        case_id: str,
        proposal_id: str | None = None,
    ) -> ActivityResult:
        """Accept a pending embargo proposal, activating the embargo."""
        req = AcceptEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            proposal_id=proposal_id,
        )
        return SvcAcceptEmbargoUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def reject_embargo(
        self,
        actor_id: str,
        case_id: str,
        proposal_id: str | None = None,
    ) -> ActivityResult:
        """Reject a pending embargo proposal."""
        req = RejectEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            proposal_id=proposal_id,
        )
        return SvcRejectEmbargoUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def propose_embargo_revision(
        self,
        actor_id: str,
        case_id: str,
        end_time: datetime,
        note: str | None = None,
    ) -> ActivityResult:
        """Propose a revision to an active embargo."""
        req = ProposeEmbargoRevisionTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            end_time=end_time,
            note=note,
        )
        return SvcProposeEmbargoRevisionUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def terminate_embargo(
        self,
        actor_id: str,
        case_id: str,
    ) -> ActivityResult:
        """Terminate an active embargo."""
        req = TerminateEmbargoTriggerRequest(
            actor_id=actor_id, case_id=case_id
        )
        return SvcTerminateEmbargoUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    # -----------------------------------------------------------------------
    # Actor / participant triggers
    # -----------------------------------------------------------------------

    def suggest_actor_to_case(
        self,
        actor_id: str,
        case_id: str,
        suggested_actor_id: str,
        roles: list | None = None,
    ) -> ActivityResult:
        """Recommend another actor to a case owner."""
        req = SuggestActorToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            suggested_actor_id=suggested_actor_id,
            roles=(
                [CVDRole(r) if isinstance(r, str) else r for r in roles]
                if roles
                else None
            ),
        )
        return SvcSuggestActorToCaseUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def accept_case_invite(
        self,
        actor_id: str,
        invite_id: str,
    ) -> ActivityResult:
        """Accept a case invitation."""
        req = AcceptCaseInviteTriggerRequest(
            actor_id=actor_id,
            invite_id=invite_id,
        )
        return SvcAcceptCaseInviteUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def reject_case_invite(
        self,
        actor_id: str,
        invite_id: str,
    ) -> ActivityResult:
        """Reject a case invitation."""
        req = RejectCaseInviteTriggerRequest(
            actor_id=actor_id,
            invite_id=invite_id,
        )
        return SvcRejectCaseInviteUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def invite_actor_to_case(
        self,
        actor_id: str,
        case_id: str,
        invitee_id: str,
        roles: list | None = None,
    ) -> ActivityResult:
        """Directly invite an actor to a case."""
        req = InviteActorToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            invitee_id=invitee_id,
            roles=roles,
        )
        return SvcInviteActorToCaseUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def offer_case_participant_role(
        self,
        actor_id: str,
        case_id: str,
        target_actor_id: str,
        role: CVDRole = CVDRole.CASE_MANAGER,
    ) -> RoleOfferResult:
        """Offer a CVDRole to a target Actor via the canonical ADR-0039 wire format.

        Emits ``Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)``.
        """
        req = OfferCaseParticipantRoleTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            target_actor_id=target_actor_id,
            role=role,
        )
        return SvcOfferCaseParticipantRoleUseCase(
            self._dl, req, trigger_activity=self._trigger_activity
        ).execute()

    def accept_actor_recommendation(
        self,
        actor_id: str,
        cp_offer_id: str,
        case_actor_id: str,
    ) -> ActivityResult:
        """Accept an actor recommendation as the Case Owner.

        Emits Accept(Offer(CaseParticipant)) to the CaseActor (ADR-0026,
        CM-16-006).
        """
        req = AcceptActorRecommendationTriggerRequest(
            actor_id=actor_id,
            cp_offer_id=cp_offer_id,
            case_actor_id=case_actor_id,
        )
        return SvcAcceptActorRecommendationUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def offer_case_ownership_transfer(
        self,
        actor_id: str,
        case_id: str,
        transferee_id: str,
        content: str | None = None,
    ) -> ActivityResult:
        """Offer case ownership to another actor (TRIG-11-001).

        Emits ``Offer(VulnerabilityCase)`` (ownership transfer variant) from
        the offering actor to ``transferee_id``.
        """
        req = OfferCaseOwnershipTransferTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            transferee_id=transferee_id,
            content=content,
        )
        return SvcOfferCaseOwnershipTransferUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()

    def accept_case_ownership_transfer(
        self,
        actor_id: str,
        offer_id: str,
    ) -> ActivityResult:
        """Accept a case ownership transfer offer (TRIG-11-002).

        Emits ``Accept(Offer(VulnerabilityCase))`` from the accepting actor
        back to the offering actor.
        """
        req = AcceptCaseOwnershipTransferTriggerRequest(
            actor_id=actor_id,
            offer_id=offer_id,
        )
        return SvcAcceptCaseOwnershipTransferUseCase(
            self._dl,
            req,
            **self._bt_ports(),
        ).execute()
