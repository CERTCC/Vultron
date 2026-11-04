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


"""Request bodies for the actor trigger verbs: recommendations, invitations,
participant roles and case ownership transfer.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from vultron.core.models._helpers import (
    require_future_aware,
    timestamp_serializer,
)
from vultron.core.models.base import NonEmptyString, UriString
from vultron.core.use_cases.triggers.request_bodies._base import (
    CaseTriggerRequest,
    _parse_optional_roles,
)
from vultron.enums.roles import CVDRole, parse_role


class SuggestActorToCaseRequest(CaseTriggerRequest):
    """Request body for the suggest-actor-to-case trigger endpoint.

    TRIG-03-001: Must include case_id and suggested_actor_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    suggested_actor_id: UriString
    roles: list[CVDRole] | None = None

    @field_validator("roles", mode="before")
    @classmethod
    def _parse_roles(cls, value: object) -> object:
        return _parse_optional_roles(value)


class AcceptCaseInviteRequest(BaseModel):
    """Request body for the accept-case-invite trigger endpoint.

    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    invite_id identifies the RmInviteToCaseActivity to accept.
    """

    model_config = ConfigDict(extra="ignore")

    invite_id: NonEmptyString


class FullCaseInviteReplyRequest(BaseModel):
    """Request body for the three full-case Invite reply trigger endpoints.

    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    invite_id identifies the full-case Invite the participant is answering
    (CM-11-010).  The reply's ledger position is this actor's own, read from
    its store; the caller does not supply it (CM-11-011).
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


class _ActorRecommendationAnswerRequest(BaseModel):
    """The body shared by the Case Owner's two answers to a recommendation.

    Both name the Offer(CaseParticipant) the CaseActor forwarded and the
    CaseActor the answer goes to (ADR-0026, CM-16-006, CM-16-007).

    TRIG-03-001: Must include cp_offer_id and case_actor_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    cp_offer_id: NonEmptyString
    case_actor_id: UriString


class AcceptActorRecommendationRequest(_ActorRecommendationAnswerRequest):
    """Request body for the accept-actor-recommendation trigger endpoint.

    Sent by the Case Owner (e.g. Vendor1) to accept an Offer(CaseParticipant)
    forwarded by the CaseActor per ADR-0026 (CM-16-006).

    TRIG-03-001: Must include cp_offer_id and case_actor_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """


class RejectActorRecommendationRequest(_ActorRecommendationAnswerRequest):
    """Request body for the reject-actor-recommendation trigger endpoint.

    Sent by the Case Owner to reject an Offer(CaseParticipant) forwarded by
    the CaseActor per ADR-0026 (CM-16-007).

    TRIG-03-001: Must include cp_offer_id and case_actor_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """


class InviteActorToCaseRequest(CaseTriggerRequest):
    """Request body for the invite-actor-to-case trigger endpoint.

    TRIG-03-001: Must include case_id and invitee_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    invitee_id: UriString
    roles: list[CVDRole] | None = None

    @field_validator("roles", mode="before")
    @classmethod
    def _parse_roles(cls, value: object) -> object:
        return _parse_optional_roles(value)


class OfferCaseParticipantRoleRequest(CaseTriggerRequest):
    """Request body for the offer-case-participant-role trigger endpoint (ADR-0039).

    Emits ``Offer(CaseParticipantRole)[context=VulnerabilityCase]``, whose
    ``target`` is ``target_actor_id``, from the requesting actor.  ``role`` is
    required: it has no default, since the CASE_MANAGER refuses an Offer of
    ``CASE_OWNER`` or ``CASE_MANAGER`` and reads no missing role as a default
    (CM-33-014).
    """

    target_actor_id: UriString
    role: CVDRole

    @field_validator("role", mode="before")
    @classmethod
    def _parse_role(cls, value: object) -> object:
        if isinstance(value, str) and not isinstance(value, CVDRole):
            return parse_role(value)
        return value


class OfferCaseOwnershipTransferRequest(CaseTriggerRequest):
    """Request body for the offer-case-ownership-transfer trigger endpoint.

    Emits the requesting Case Owner's proposal,
    ``Offer(Offer(VulnerabilityCase))``, to the case's CASE_MANAGER, which
    offers the case to the specified transferee (TRIG-11-001, ADR-0148).

    TRIG-03-001: Must include case_id and transferee_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    TRIG-11-007: Optional end_time, timezone-aware and in the future, is the
    deadline to answer the Offer (CM-21-016); it is held in UTC.
    """

    transferee_id: UriString
    content: NonEmptyString | None = None
    end_time: datetime | None = None
    _serialize_end_time = timestamp_serializer("end_time")

    @field_validator("end_time")
    @classmethod
    def end_time_must_be_tz_aware_and_future(
        cls, v: datetime | None
    ) -> datetime | None:
        deadline = require_future_aware(v)
        return deadline.astimezone(UTC) if deadline is not None else None


class _OwnershipTransferAnswerRequest(BaseModel):
    """The body shared by every ownership-transfer reply: it names what it answers.

    The transferee's two answers name the CASE_MANAGER's Offer; the owner's
    withdrawal names its own proposal (ADR-0148).

    TRIG-03-001: Must include offer_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    offer_id: NonEmptyString


class AcceptCaseOwnershipTransferRequest(_OwnershipTransferAnswerRequest):
    """Request body for the accept-case-ownership-transfer trigger endpoint.

    Emits ``Accept(Offer(VulnerabilityCase))`` from the requesting actor,
    addressed to the case's CASE_MANAGER (TRIG-11-002, CM-21-006).

    TRIG-03-001: Must include offer_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """


class RejectCaseOwnershipTransferRequest(_OwnershipTransferAnswerRequest):
    """Request body for the reject-case-ownership-transfer trigger endpoint.

    Emits ``Reject(Offer(VulnerabilityCase))`` from the requesting actor,
    addressed to the case's CASE_MANAGER (TRIG-11-005, CM-21-010).

    TRIG-03-001: Must include offer_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """


class WithdrawCaseOwnershipTransferRequest(_OwnershipTransferAnswerRequest):
    """Request body for the withdraw-case-ownership-transfer trigger endpoint.

    Emits ``Undo(Offer(Offer(VulnerabilityCase)))`` from the requesting
    actor — the Case Owner that made the proposal — addressed to the case's
    CASE_MANAGER (TRIG-11-006, CM-21-015).  ``offer_id`` names that
    proposal, the activity the offer trigger returned (ADR-0148).

    TRIG-03-001: Must include offer_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """
