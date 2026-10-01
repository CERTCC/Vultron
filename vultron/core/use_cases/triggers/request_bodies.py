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

"""Trigger request body models — the single request-model family's bases.

Each class here is one trigger verb's request body: the fields a client sends,
without ``actor_id``, which is the URL path parameter and never a body field
(TRIG-06-001). The class names are OpenAPI component names and are frozen by
the golden snapshot (TRIG-12-003), so a rename here is a contract change.

The bodies live in core, not in the FastAPI adapter, because the core
``*TriggerRequest`` models in :mod:`vultron.core.use_cases.triggers.requests`
derive from them and add ``actor_id`` (ADR-0110): one family, one
``CaseTriggerRequest``, one ``end_time`` validator. Core MUST NOT import the
adapter layer (ARCH-03-001), so the base of the family is defined here and
``vultron/adapters/driving/fastapi/trigger_models.py`` re-exports it under the
names the routers and the OpenAPI document already use.

The models are declared as classes, not built with ``create_model``: FastAPI
renders each class docstring as the component schema ``description``, and
``create_model`` would drop it.

CS-09-002: ValidateReportRequest, InvalidateReportRequest, and
CloseReportRequest share a common base (ReportTriggerRequest) because they
have identical fields.  RejectReportRequest also uses offer_id but requires
a non-optional note field.
"""

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from vultron.core.models.base import NonEmptyString, UriString
from vultron.core.states.cs import CS_d, CS_vf
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class ReportTriggerRequest(BaseModel):
    """
    Shared base for report-level trigger requests.

    TRIG-03-001: Must include offer_id to identify the target offer.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    TRIG-03-003: Optional note field may be included.
    """

    model_config = ConfigDict(extra="ignore")

    offer_id: NonEmptyString
    note: NonEmptyString | None = None


class ValidateReportRequest(ReportTriggerRequest):
    """Request body for the validate-report trigger endpoint."""


class InvalidateReportRequest(ReportTriggerRequest):
    """Request body for the invalidate-report trigger endpoint."""


class CloseReportRequest(ReportTriggerRequest):
    """
    Request body for the close-report trigger endpoint.

    Distinction from reject-report: close-report closes a report after the
    RM lifecycle has proceeded (RM → C transition; emits RC message), while
    reject-report hard-rejects an incoming offer before validation completes.
    """


class RejectReportRequest(BaseModel):
    """
    Request body for the reject-report trigger endpoint.

    TRIG-03-001: Must include offer_id to identify the target offer.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    TRIG-03-004: note is required (hard-close decisions warrant documented
        justification); an empty note emits a WARNING.
    """

    model_config = ConfigDict(extra="ignore")

    offer_id: NonEmptyString
    note: str

    @field_validator("note")
    @classmethod
    def note_must_be_present(cls, v: str) -> str:
        if not v.strip():
            logger.warning(
                "reject-report trigger received an empty note field; "
                "hard-close decisions should include a documented reason."
            )
        return v


class CaseTriggerRequest(BaseModel):
    """
    Request body for case-level trigger endpoints.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    case_id: UriString


class ProposeEmbargoRequest(CaseTriggerRequest):
    """
    Request body for the propose-embargo trigger endpoint.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    TRIG-03-003: Optional note field may be included.
    end_time is required and must be timezone-aware and in the future.
    """

    note: NonEmptyString | None = None
    end_time: datetime

    @field_validator("end_time")
    @classmethod
    def end_time_must_be_tz_aware_and_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("end_time must be timezone-aware")
        if v <= datetime.now(tz=timezone.utc):
            raise ValueError("end_time must be in the future")
        return v


class AcceptEmbargoRequest(CaseTriggerRequest):
    """
    Request body for the accept-embargo trigger endpoint.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    Optional proposal_id identifies the specific EmProposeEmbargoActivity to accept;
    if omitted, the earliest-expiring open proposal for the case is used
    (EP-08-002) — never the first recorded.
    """

    proposal_id: NonEmptyString | None = None


# Backward-compatible alias
EvaluateEmbargoRequest = AcceptEmbargoRequest


class RejectEmbargoRequest(CaseTriggerRequest):
    """
    Request body for the reject-embargo trigger endpoint.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    Optional proposal_id identifies the specific EmProposeEmbargoActivity to reject;
    if omitted, the earliest-expiring open proposal for the case is used
    (EP-08-002) — never the first recorded.
    """

    proposal_id: NonEmptyString | None = None


class ProposeEmbargoRevisionRequest(ProposeEmbargoRequest):
    """
    Request body for the propose-embargo-revision trigger endpoint.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    end_time is required and must be timezone-aware and in the future.
    Only valid when EM state is ACTIVE or REVISE; use propose-embargo for
    initial proposals.
    """


class TerminateEmbargoRequest(CaseTriggerRequest):
    """
    Request body for the terminate-embargo trigger endpoint.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """


class SubmitReportRequest(BaseModel):
    """Request body for the submit-report trigger endpoint.

    The finder uses this to create a VulnerabilityReport and offer it to a
    recipient.  The actor_id is taken from the URL path; report_name,
    report_content, and recipient_id must be supplied in the request body.

    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    report_name: NonEmptyString
    report_content: NonEmptyString
    recipient_id: UriString


class AddObjectToCaseRequest(CaseTriggerRequest):
    """Request body for the add-object-to-case general trigger endpoint.

    Accepts any existing AS2 object identified by ``object_id``.  The object
    must already exist in the actor's datalayer.  Type-specific convenience
    endpoints (e.g., ``add-report-to-case``) delegate to this after
    performing their own type validation (TRIG-10-001, TRIG-10-002).

    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    object_id: NonEmptyString


class AddNoteToCaseRequest(CaseTriggerRequest):
    """Request body for the add-note-to-case trigger endpoint.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    note_name: NonEmptyString
    note_content: NonEmptyString
    in_reply_to: NonEmptyString | None = None


class CreateCaseRequest(BaseModel):
    """Request body for the create-case trigger endpoint.

    The actor creates a local VulnerabilityCase and queues a
    CreateCaseActivity in their outbox for delivery to the CaseActor.

    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    name: NonEmptyString
    content: NonEmptyString
    report_id: NonEmptyString | None = None
    to: list[str] | None = None


class AddReportToCaseRequest(CaseTriggerRequest):
    """Request body for the add-report-to-case trigger endpoint.

    TRIG-03-001: Must include case_id and report_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    report_id: NonEmptyString


class SuggestActorToCaseRequest(CaseTriggerRequest):
    """Request body for the suggest-actor-to-case trigger endpoint.

    TRIG-03-001: Must include case_id and suggested_actor_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    suggested_actor_id: UriString
    roles: list[CVDRole] | None = None


class AcceptCaseInviteRequest(BaseModel):
    """Request body for the accept-case-invite trigger endpoint.

    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    invite_id identifies the RmInviteToCaseActivity to accept.
    """

    model_config = ConfigDict(extra="ignore")

    invite_id: NonEmptyString


class RejectCaseInviteRequest(BaseModel):
    """Request body for the reject-case-invite trigger endpoint.

    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    invite_id identifies the RmInviteToCaseActivity to reject.
    """

    model_config = ConfigDict(extra="ignore")

    invite_id: NonEmptyString


class AcceptActorRecommendationRequest(BaseModel):
    """Request body for the accept-actor-recommendation trigger endpoint.

    Sent by the Case Owner (e.g. Vendor1) to accept an Offer(CaseParticipant)
    forwarded by the CaseActor per ADR-0026 (CM-16-006).

    TRIG-03-001: Must include cp_offer_id and case_actor_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    cp_offer_id: NonEmptyString
    case_actor_id: UriString


class InviteActorToCaseRequest(CaseTriggerRequest):
    """Request body for the invite-actor-to-case trigger endpoint.

    TRIG-03-001: Must include case_id and invitee_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    invitee_id: UriString
    roles: list[CVDRole] | None = None


class OfferCaseParticipantRoleRequest(CaseTriggerRequest):
    """Request body for the offer-case-participant-role trigger endpoint (ADR-0039).

    Emits ``Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)``
    from the requesting actor.  ``role`` defaults to ``"CASE_MANAGER"`` for
    backward-compatibility with callers that previously used the deprecated
    offer-case-manager-role endpoint.
    """

    target_actor_id: UriString
    role: CVDRole = CVDRole.CASE_MANAGER


class OfferCaseOwnershipTransferRequest(CaseTriggerRequest):
    """Request body for the offer-case-ownership-transfer trigger endpoint.

    Emits ``Offer(VulnerabilityCase)`` (ownership transfer variant) from the
    requesting actor to the specified transferee (TRIG-11-001).

    TRIG-03-001: Must include case_id and transferee_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    transferee_id: UriString
    content: NonEmptyString | None = None


class AcceptCaseOwnershipTransferRequest(BaseModel):
    """Request body for the accept-case-ownership-transfer trigger endpoint.

    Emits ``Accept(Offer(VulnerabilityCase))`` from the requesting actor back
    to the offering actor (TRIG-11-002).

    TRIG-03-001: Must include offer_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    offer_id: NonEmptyString


class AddOnBehalfStatusRequest(CaseTriggerRequest):
    """Request body for the add-on-behalf-status trigger.

    A Case Manager or Case Owner records a vendor's awareness (``v→V``,
    ``vf_state="Vf"``) or a deployer's deployment (``d→D``, ``d_state="D"``)
    on behalf of an actor that was notified or invited but has not joined the
    case (ADR-0084; PRM-06-003, PRM-06-004).  ``target_actor_id`` names that
    actor.  Only the upward rungs are assertable on another actor's behalf:
    ``vf_state`` must be ``"Vf"`` and ``d_state`` must be ``"D"``.
    ``vf_state="VF"`` (``f→F``) is refused because fix readiness is not
    externally knowable and is only ever self-declared by the Vendor-role
    holder (PRM-06-005); the lower rungs (``"vf"``, ``"d"``) are refused
    because recording unawareness or non-deployment on someone's behalf is
    not an assertion PRM-06 permits.  At least one of ``vf_state`` /
    ``d_state`` is required.

    TRIG-03-002: Unknown fields are silently ignored.
    """

    target_actor_id: UriString
    vf_state: CS_vf | None = None
    d_state: CS_d | None = None

    @field_validator("vf_state")
    @classmethod
    def vf_state_not_fix_ready(cls, v: CS_vf | None) -> CS_vf | None:
        if v is not None and v == CS_vf.VF:
            raise ValueError(
                "f→F (CS_vf.VF) cannot be asserted on behalf of another actor"
                " (ADR-0084, PRM-06-005)"
            )
        if v is not None and v != CS_vf.Vf:
            raise ValueError(
                "only v→V (CS_vf.Vf) may be asserted on behalf of a vendor"
                f" (PRM-06-003); got {v!r}"
            )
        return v

    @field_validator("d_state")
    @classmethod
    def d_state_is_deployed(cls, v: CS_d | None) -> CS_d | None:
        if v is not None and v != CS_d.D:
            raise ValueError(
                "only d→D (CS_d.D) may be asserted on behalf of a deployer"
                f" (PRM-06-004); got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def at_least_one_dimension(self) -> "AddOnBehalfStatusRequest":
        if self.vf_state is None and self.d_state is None:
            raise ValueError(
                "at least one of vf_state or d_state must be provided"
                " (PRM-06-003/004)"
            )
        return self


class NotifyFixReadyRequest(CaseTriggerRequest):
    """Request body for the notify-fix-ready demo trigger.

    Signals that the vendor has a fix ready (VFD → VFd).
    TRIG-03-002: Unknown fields are silently ignored.
    """


class NotifyFixDeployedRequest(CaseTriggerRequest):
    """Request body for the notify-fix-deployed demo trigger.

    Signals that the fix has been deployed (VFd → VFD).
    TRIG-03-002: Unknown fields are silently ignored.
    """


class NotifyPublishedRequest(CaseTriggerRequest):
    """Request body for the notify-published demo trigger.

    Signals that the vulnerability has been publicly disclosed (CS.VFDPxa).
    TRIG-03-002: Unknown fields are silently ignored.
    """


class CloseCaseRequest(CaseTriggerRequest):
    """Request body for the close-case demo trigger.

    Signals that the actor is closing the case (RM → CLOSED).
    TRIG-03-002: Unknown fields are silently ignored.
    """


class SyncLogEntryRequest(CaseTriggerRequest):
    """Request body for the demo sync-log-entry trigger.

    Commits a canonical case ledger entry and fans it out to all participants
    via Announce(CaseLedgerEntry). Uses Announce(VulnerabilityCase) as the
    canonical payload type (case-actor-authored).

    TRIG-03-002: Unknown fields are silently ignored.
    """

    object_id: UriString
    event_type: NonEmptyString
