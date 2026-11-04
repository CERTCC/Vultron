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

"""Core trigger requests for the actor verbs: recommendations, invitations,
participant roles and case ownership transfer.
"""

from vultron.core.models.use_case_result import (
    ActivityResult,
    RoleOfferResult,
)
from vultron.core.use_cases.triggers.request_bodies import (
    AcceptActorRecommendationRequest,
    AcceptCaseInviteRequest,
    AcceptCaseOwnershipTransferRequest,
    FullCaseInviteReplyRequest,
    InviteActorToCaseRequest,
    OfferCaseOwnershipTransferRequest,
    OfferCaseParticipantRoleRequest,
    RejectActorRecommendationRequest,
    RejectCaseInviteRequest,
    RejectCaseOwnershipTransferRequest,
    SuggestActorToCaseRequest,
    WithdrawCaseOwnershipTransferRequest,
)
from vultron.core.use_cases.triggers.requests._base import TriggerRequest


class SuggestActorToCaseTriggerRequest(
    TriggerRequest[ActivityResult], SuggestActorToCaseRequest
):
    """Trigger request for an actor to recommend another actor to a case.

    Emits a RecommendActorActivity addressed to the Case Actor, which then
    autonomously invites the suggested actor.
    """


class AcceptCaseInviteTriggerRequest(
    TriggerRequest[ActivityResult], AcceptCaseInviteRequest
):
    """Trigger request for an invitee to accept a case invitation.

    Emits an RmAcceptInviteToCaseActivity queued in the actor's outbox for
    delivery to the Case Actor that issued the invitation.
    """


class RejectCaseInviteTriggerRequest(
    TriggerRequest[ActivityResult], RejectCaseInviteRequest
):
    """Trigger request for an invitee to reject a case invitation.

    Emits an RmRejectInviteToCaseActivity queued in the actor's outbox for
    delivery to the Case Actor that issued the invitation.
    """


class AcceptFullCaseInviteTriggerRequest(
    TriggerRequest[ActivityResult], FullCaseInviteReplyRequest
):
    """Trigger request for a joined participant to judge the case valid (RV).

    Emits ``Accept(full-case Invite)`` carrying the participant's own ledger
    position, queued in its outbox for the CASE_MANAGER (CM-11-011).
    """


class TentativeRejectFullCaseInviteTriggerRequest(
    TriggerRequest[ActivityResult], FullCaseInviteReplyRequest
):
    """Trigger request for a joined participant to judge the case invalid (RI).

    Emits ``TentativeReject(full-case Invite)`` carrying the participant's own
    ledger position (CM-11-011).
    """


class RejectFullCaseInviteTriggerRequest(
    TriggerRequest[ActivityResult], FullCaseInviteReplyRequest
):
    """Trigger request for a joined participant to close the case (RC).

    Emits ``Reject(full-case Invite)`` carrying the participant's own ledger
    position (CM-11-011).
    """


class AcceptActorRecommendationTriggerRequest(
    TriggerRequest[ActivityResult], AcceptActorRecommendationRequest
):
    """Trigger request for the Case Owner to accept an actor recommendation.

    Emits an Accept(Offer(CaseParticipant)) queued in the Case Owner's outbox
    for delivery to the CaseActor (ADR-0026, CM-16-006).
    """


class RejectActorRecommendationTriggerRequest(
    TriggerRequest[ActivityResult], RejectActorRecommendationRequest
):
    """Trigger request for the Case Owner to reject an actor recommendation.

    Emits a Reject(Offer(CaseParticipant)) queued in the Case Owner's outbox
    for delivery to the CaseActor (ADR-0026, CM-16-007).
    """


class InviteActorToCaseTriggerRequest(
    TriggerRequest[ActivityResult], InviteActorToCaseRequest
):
    """Trigger request for the case owner to directly invite an actor.

    Emits an RmInviteToCaseActivity addressed to the invitee, queued in the
    actor's outbox for delivery.
    """


class OfferCaseParticipantRoleTriggerRequest(
    TriggerRequest[RoleOfferResult], OfferCaseParticipantRoleRequest
):
    """Trigger request to offer a CVDRole to a target Actor in a Case.

    Emits ``Offer(CaseParticipantRole)[context=VulnerabilityCase]``, whose
    ``target`` is the target Actor, from the requesting actor (ADR-0039).
    """


class OfferCaseOwnershipTransferTriggerRequest(
    TriggerRequest[ActivityResult], OfferCaseOwnershipTransferRequest
):
    """Trigger request to offer case ownership to another actor.

    Emits the requesting Case Owner's proposal,
    ``Offer(Offer(VulnerabilityCase))``, to the case's CASE_MANAGER, which
    offers the case to ``transferee_id`` (TRIG-11-001, ADR-0148).
    """


class AcceptCaseOwnershipTransferTriggerRequest(
    TriggerRequest[ActivityResult], AcceptCaseOwnershipTransferRequest
):
    """Trigger request to accept a case ownership transfer offer.

    Emits ``Accept(Offer(VulnerabilityCase))`` from the requesting actor,
    addressed to the case's CASE_MANAGER (TRIG-11-002, CM-21-006).
    """


class RejectCaseOwnershipTransferTriggerRequest(
    TriggerRequest[ActivityResult], RejectCaseOwnershipTransferRequest
):
    """Trigger request to decline a case ownership transfer offer.

    Emits ``Reject(Offer(VulnerabilityCase))`` from the requesting actor,
    addressed to the case's CASE_MANAGER (TRIG-11-005, CM-21-010).
    """


class WithdrawCaseOwnershipTransferTriggerRequest(
    TriggerRequest[ActivityResult], WithdrawCaseOwnershipTransferRequest
):
    """Trigger request to withdraw an open case ownership transfer offer.

    Emits ``Undo(Offer(Offer(VulnerabilityCase)))`` of the requesting
    actor's own proposal, addressed to the case's CASE_MANAGER (TRIG-11-006,
    CM-21-015).
    """
