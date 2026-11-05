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
(TRIG-06-001). The class names are the OpenAPI component names clients read,
so a rename here is a contract change.

The bodies live in core, not in the FastAPI adapter, because the core
``*TriggerRequest`` models in :mod:`vultron.core.use_cases.triggers.requests`
derive from them and add ``actor_id`` (ADR-0110): one family, one
``CaseTriggerRequest``, one ``end_time`` validator. Core MUST NOT import the
adapter layer (ARCH-03-001), so the base of the family is defined here and the
FastAPI routers import it from here under the names the OpenAPI document
already uses.

The models are declared as classes, not built with ``create_model``: FastAPI
renders each class docstring as the component schema ``description``, and
``create_model`` would drop it.

The bodies are grouped by trigger domain, one submodule each
(:mod:`.report`, :mod:`.embargo`, :mod:`.case`, :mod:`.actor`), over the
shared bases in :mod:`._base`; this package re-exports every body model.
"""

from ._base import (
    CaseTriggerRequest,
)
from .actor import (
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
from .case import (
    AddNoteToCaseRequest,
    AddObjectToCaseRequest,
    AddOnBehalfStatusRequest,
    AddReportToCaseRequest,
    CreateCaseRequest,
    LeaveCaseRequest,
    NotifyFixDeployedRequest,
    NotifyFixReadyRequest,
    NotifyPublishedRequest,
    SetStubSummaryRequest,
    SyncLogEntryRequest,
)
from .embargo import (
    AcceptEmbargoRequest,
    ProposeEmbargoRequest,
    ProposeEmbargoRevisionRequest,
    RejectEmbargoRequest,
    TerminateEmbargoRequest,
    WithdrawEmbargoRequest,
)
from .report import (
    AckReportRequest,
    InvalidateReportRequest,
    RejectReportRequest,
    ReportTriggerRequest,
    SubmitReportRequest,
    ValidateReportRequest,
)

__all__ = [
    "AcceptActorRecommendationRequest",
    "AcceptCaseInviteRequest",
    "AcceptCaseOwnershipTransferRequest",
    "AcceptEmbargoRequest",
    "AckReportRequest",
    "AddNoteToCaseRequest",
    "AddObjectToCaseRequest",
    "AddOnBehalfStatusRequest",
    "AddReportToCaseRequest",
    "CaseTriggerRequest",
    "CreateCaseRequest",
    "FullCaseInviteReplyRequest",
    "InvalidateReportRequest",
    "InviteActorToCaseRequest",
    "LeaveCaseRequest",
    "NotifyFixDeployedRequest",
    "NotifyFixReadyRequest",
    "NotifyPublishedRequest",
    "OfferCaseOwnershipTransferRequest",
    "OfferCaseParticipantRoleRequest",
    "ProposeEmbargoRequest",
    "ProposeEmbargoRevisionRequest",
    "RejectActorRecommendationRequest",
    "RejectCaseInviteRequest",
    "RejectCaseOwnershipTransferRequest",
    "RejectEmbargoRequest",
    "RejectReportRequest",
    "ReportTriggerRequest",
    "SetStubSummaryRequest",
    "SubmitReportRequest",
    "SuggestActorToCaseRequest",
    "SyncLogEntryRequest",
    "TerminateEmbargoRequest",
    "ValidateReportRequest",
    "WithdrawCaseOwnershipTransferRequest",
    "WithdrawEmbargoRequest",
]
