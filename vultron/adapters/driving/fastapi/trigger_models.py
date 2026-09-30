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

"""
HTTP request body models for trigger endpoints.

These are the request body schemas the FastAPI trigger routers validate.  They
intentionally omit ``actor_id``, which routers obtain from the URL path
(TRIG-06-001).  Their class names are OpenAPI component names, frozen by the
golden snapshot (TRIG-12-003).

The classes are defined once, in core
(:mod:`vultron.core.use_cases.triggers.request_bodies`), because the core
``*TriggerRequest`` models derive from them (ADR-0110) and core MUST NOT import
the adapter layer (ARCH-03-001).  This module re-exports them so every router
and test keeps importing the body models from the adapter path.  Add a new body
model there, then list it here.
"""

from vultron.core.use_cases.triggers.request_bodies import (
    AcceptActorRecommendationRequest,
    AcceptCaseInviteRequest,
    AcceptCaseOwnershipTransferRequest,
    AcceptEmbargoRequest,
    AddNoteToCaseRequest,
    AddObjectToCaseRequest,
    AddReportToCaseRequest,
    CaseTriggerRequest,
    CloseCaseRequest,
    CloseReportRequest,
    CreateCaseRequest,
    EvaluateEmbargoRequest,
    InvalidateReportRequest,
    InviteActorToCaseRequest,
    NotifyFixDeployedRequest,
    NotifyFixReadyRequest,
    NotifyPublishedRequest,
    OfferCaseOwnershipTransferRequest,
    OfferCaseParticipantRoleRequest,
    ProposeEmbargoRequest,
    ProposeEmbargoRevisionRequest,
    RejectCaseInviteRequest,
    RejectEmbargoRequest,
    RejectReportRequest,
    ReportTriggerRequest,
    SubmitReportRequest,
    SuggestActorToCaseRequest,
    SyncLogEntryRequest,
    TerminateEmbargoRequest,
    ValidateReportRequest,
)

__all__ = [
    "AcceptActorRecommendationRequest",
    "AcceptCaseInviteRequest",
    "AcceptCaseOwnershipTransferRequest",
    "AcceptEmbargoRequest",
    "AddNoteToCaseRequest",
    "AddObjectToCaseRequest",
    "AddReportToCaseRequest",
    "CaseTriggerRequest",
    "CloseCaseRequest",
    "CloseReportRequest",
    "CreateCaseRequest",
    "EvaluateEmbargoRequest",
    "InvalidateReportRequest",
    "InviteActorToCaseRequest",
    "NotifyFixDeployedRequest",
    "NotifyFixReadyRequest",
    "NotifyPublishedRequest",
    "OfferCaseOwnershipTransferRequest",
    "OfferCaseParticipantRoleRequest",
    "ProposeEmbargoRequest",
    "ProposeEmbargoRevisionRequest",
    "RejectCaseInviteRequest",
    "RejectEmbargoRequest",
    "RejectReportRequest",
    "ReportTriggerRequest",
    "SubmitReportRequest",
    "SuggestActorToCaseRequest",
    "SyncLogEntryRequest",
    "TerminateEmbargoRequest",
    "ValidateReportRequest",
]
