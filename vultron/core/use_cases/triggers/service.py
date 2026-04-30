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
a single :class:`~vultron.core.ports.datalayer.DataLayer` at construction and
exposes all 18 trigger operations plus ``commit_log_entry`` as named methods.

Callers (FastAPI routers, CLI adapters, domain tests) construct a
``TriggerService`` directly::

    svc = TriggerService(dl)
    result = svc.propose_embargo(actor_id=..., case_id=..., end_time=...)

Domain errors bubble up as bare ``VultronError`` subclasses; the HTTP adapter
layer translates them via ``domain_error_translation()``.

No HTTP framework imports permitted in this module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases.triggers.actor import (
    SvcAcceptCaseInviteUseCase,
    SvcInviteActorToCaseUseCase,
    SvcSuggestActorToCaseUseCase,
)
from vultron.core.use_cases.triggers.case import (
    SvcAddReportToCaseUseCase,
    SvcCreateCaseUseCase,
    SvcDeferCaseUseCase,
    SvcEngageCaseUseCase,
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
    SvcCloseReportUseCase,
    SvcInvalidateReportUseCase,
    SvcRejectReportUseCase,
    SvcSubmitReportUseCase,
    SvcValidateReportUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptCaseInviteTriggerRequest,
    AcceptEmbargoTriggerRequest,
    AddNoteToCaseTriggerRequest,
    AddReportToCaseTriggerRequest,
    CloseReportTriggerRequest,
    CreateCaseTriggerRequest,
    DeferCaseTriggerRequest,
    EngageCaseTriggerRequest,
    InvalidateReportTriggerRequest,
    InviteActorToCaseTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
    RejectReportTriggerRequest,
    SubmitReportTriggerRequest,
    SuggestActorToCaseTriggerRequest,
    TerminateEmbargoTriggerRequest,
    ValidateReportTriggerRequest,
)
from vultron.core.use_cases.triggers.sync import commit_log_entry_trigger


class TriggerService:
    """Facade over all actor-initiated trigger use cases.

    Accepts a single :class:`~vultron.core.ports.datalayer.DataLayer` at
    construction; exposes every trigger operation as a named method.  Hides
    the 18 ``SvcXxx`` use-case class names, the ``XxxTriggerRequest``
    hierarchy, and the ``(dl, request).execute()`` dispatch protocol from
    callers.

    Raises bare ``VultronError`` subclasses — HTTP adapters translate these
    via ``domain_error_translation()``.
    """

    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    # -----------------------------------------------------------------------
    # Report triggers
    # -----------------------------------------------------------------------

    def submit_report(
        self,
        actor_id: str,
        report_name: str,
        report_content: str,
        recipient_id: str,
    ) -> dict[str, Any]:
        """Create a VulnerabilityReport and offer it to *recipient_id*."""
        req = SubmitReportTriggerRequest(
            actor_id=actor_id,
            report_name=report_name,
            report_content=report_content,
            recipient_id=recipient_id,
        )
        return SvcSubmitReportUseCase(self._dl, req).execute()

    def validate_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Validate a received report offer, transitioning RM state."""
        req = ValidateReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note
        )
        return SvcValidateReportUseCase(self._dl, req).execute()

    def invalidate_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Mark a received report offer as invalid."""
        req = InvalidateReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note
        )
        return SvcInvalidateReportUseCase(self._dl, req).execute()

    def reject_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Hard-close a report offer before validation completes."""
        req = RejectReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note or None
        )
        return SvcRejectReportUseCase(self._dl, req).execute()

    def close_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Close a report that has progressed through the RM lifecycle."""
        req = CloseReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note
        )
        return SvcCloseReportUseCase(self._dl, req).execute()

    # -----------------------------------------------------------------------
    # Case triggers
    # -----------------------------------------------------------------------

    def create_case(
        self,
        actor_id: str,
        name: str,
        content: str,
        report_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a local VulnerabilityCase and queue it for the CaseActor."""
        req = CreateCaseTriggerRequest(
            actor_id=actor_id,
            name=name,
            content=content,
            report_id=report_id,
        )
        return SvcCreateCaseUseCase(self._dl, req).execute()

    def engage_case(
        self,
        actor_id: str,
        case_id: str,
    ) -> dict[str, Any]:
        """Accept a case, transitioning RM state to ACCEPTED."""
        req = EngageCaseTriggerRequest(actor_id=actor_id, case_id=case_id)
        return SvcEngageCaseUseCase(self._dl, req).execute()

    def defer_case(
        self,
        actor_id: str,
        case_id: str,
    ) -> dict[str, Any]:
        """Defer a case, transitioning RM state to DEFERRED."""
        req = DeferCaseTriggerRequest(actor_id=actor_id, case_id=case_id)
        return SvcDeferCaseUseCase(self._dl, req).execute()

    def add_report_to_case(
        self,
        actor_id: str,
        case_id: str,
        report_id: str,
    ) -> dict[str, Any]:
        """Link a VulnerabilityReport to an existing VulnerabilityCase."""
        req = AddReportToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            report_id=report_id,
        )
        return SvcAddReportToCaseUseCase(self._dl, req).execute()

    def add_note_to_case(
        self,
        actor_id: str,
        case_id: str,
        note_name: str,
        note_content: str,
        in_reply_to: str | None = None,
    ) -> dict[str, Any]:
        """Create a Note and add it to a case."""
        req = AddNoteToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            note_name=note_name,
            note_content=note_content,
            in_reply_to=in_reply_to,
        )
        return SvcAddNoteToCaseUseCase(self._dl, req).execute()

    # -----------------------------------------------------------------------
    # Embargo triggers
    # -----------------------------------------------------------------------

    def propose_embargo(
        self,
        actor_id: str,
        case_id: str,
        end_time: datetime,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Propose a new embargo or revision to an active embargo."""
        req = ProposeEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            end_time=end_time,
            note=note,
        )
        return SvcProposeEmbargoUseCase(self._dl, req).execute()

    def accept_embargo(
        self,
        actor_id: str,
        case_id: str,
        proposal_id: str | None = None,
    ) -> dict[str, Any]:
        """Accept a pending embargo proposal, activating the embargo."""
        req = AcceptEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            proposal_id=proposal_id,
        )
        return SvcAcceptEmbargoUseCase(self._dl, req).execute()

    def reject_embargo(
        self,
        actor_id: str,
        case_id: str,
        proposal_id: str | None = None,
    ) -> dict[str, Any]:
        """Reject a pending embargo proposal."""
        req = RejectEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            proposal_id=proposal_id,
        )
        return SvcRejectEmbargoUseCase(self._dl, req).execute()

    def propose_embargo_revision(
        self,
        actor_id: str,
        case_id: str,
        end_time: datetime,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Propose a revision to an active embargo."""
        req = ProposeEmbargoRevisionTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            end_time=end_time,
            note=note,
        )
        return SvcProposeEmbargoRevisionUseCase(self._dl, req).execute()

    def terminate_embargo(
        self,
        actor_id: str,
        case_id: str,
    ) -> dict[str, Any]:
        """Terminate an active embargo."""
        req = TerminateEmbargoTriggerRequest(
            actor_id=actor_id, case_id=case_id
        )
        return SvcTerminateEmbargoUseCase(self._dl, req).execute()

    # -----------------------------------------------------------------------
    # Actor / participant triggers
    # -----------------------------------------------------------------------

    def suggest_actor_to_case(
        self,
        actor_id: str,
        case_id: str,
        suggested_actor_id: str,
    ) -> dict[str, Any]:
        """Recommend another actor to a case owner."""
        req = SuggestActorToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            suggested_actor_id=suggested_actor_id,
        )
        return SvcSuggestActorToCaseUseCase(self._dl, req).execute()

    def accept_case_invite(
        self,
        actor_id: str,
        invite_id: str,
    ) -> dict[str, Any]:
        """Accept a case invitation."""
        req = AcceptCaseInviteTriggerRequest(
            actor_id=actor_id,
            invite_id=invite_id,
        )
        return SvcAcceptCaseInviteUseCase(self._dl, req).execute()

    def invite_actor_to_case(
        self,
        actor_id: str,
        case_id: str,
        invitee_id: str,
    ) -> dict[str, Any]:
        """Directly invite an actor to a case."""
        req = InviteActorToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=case_id,
            invitee_id=invitee_id,
        )
        return SvcInviteActorToCaseUseCase(self._dl, req).execute()

    # -----------------------------------------------------------------------
    # Sync / log-replication triggers
    # -----------------------------------------------------------------------

    def commit_log_entry(
        self,
        case_id: str,
        object_id: str,
        event_type: str,
        actor_id: str,
        payload_snapshot: dict[str, Any] | None = None,
        term: int | None = None,
        reason_code: str | None = None,
        reason_detail: str | None = None,
        disposition: str = "recorded",
    ) -> VultronCaseLogEntry:
        """Commit a new log entry and fan it out to all case participants."""
        return commit_log_entry_trigger(
            case_id=case_id,
            object_id=object_id,
            event_type=event_type,
            actor_id=actor_id,
            dl=cast(CaseOutboxPersistence, self._dl),
            payload_snapshot=payload_snapshot,
            term=term,
            reason_code=reason_code,
            reason_detail=reason_detail,
            disposition=disposition,
        )
