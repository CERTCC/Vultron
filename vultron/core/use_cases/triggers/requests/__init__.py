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

"""Domain request models for trigger use cases.

These are core-layer domain models (no HTTP imports) that carry every
parameter a trigger use case needs, including ``actor_id``.  Each one derives
from the verb's request *body* model in
:mod:`vultron.core.use_cases.triggers.request_bodies` — the class FastAPI
validates the HTTP body against — and adds ``actor_id`` through
:class:`TriggerRequest`.  The two families are therefore one
(ADR-0110): the body model owns the fields and their validators (the
``end_time`` rule is declared once, on ``ProposeEmbargoRequest``), and
``CaseTriggerRequest`` is defined once and re-exported here for its existing
importers.

``TriggerRequest`` is generic in the result type its verb's use case returns.
``ResultT_co`` is bound to :class:`TriggerResult` and covariant, so a single
``trigger(request: TriggerRequest[ResultT_co]) -> ResultT_co`` signature
resolves each verb's result subtype statically (UCORG-05-006 groundwork);
:func:`result_type_of` recovers the same binding at runtime.

``actor_id`` is the local actor initiating the action, injected by the
driving adapter from the URL path, never from the body (TRIG-06-001).

The requests are grouped by trigger domain, one submodule each
(:mod:`.report`, :mod:`.embargo`, :mod:`.case`, :mod:`.actor`), mirroring
:mod:`vultron.core.use_cases.triggers.request_bodies`, over the generic base
in :mod:`._base`; this package re-exports every request.
"""

from vultron.core.use_cases.triggers.request_bodies import (
    CaseTriggerRequest,
)

from ._base import (
    ResultT_co,
    TriggerRequest,
    result_type_of,
)
from .actor import (
    AcceptActorRecommendationTriggerRequest,
    AcceptCaseInviteTriggerRequest,
    AcceptCaseOwnershipTransferTriggerRequest,
    AcceptFullCaseInviteTriggerRequest,
    InviteActorToCaseTriggerRequest,
    OfferCaseOwnershipTransferTriggerRequest,
    OfferCaseParticipantRoleTriggerRequest,
    RejectActorRecommendationTriggerRequest,
    RejectCaseInviteTriggerRequest,
    RejectCaseOwnershipTransferTriggerRequest,
    RejectFullCaseInviteTriggerRequest,
    SuggestActorToCaseTriggerRequest,
    TentativeRejectFullCaseInviteTriggerRequest,
    WithdrawCaseOwnershipTransferTriggerRequest,
)
from .case import (
    AddNoteToCaseTriggerRequest,
    AddObjectToCaseTriggerRequest,
    AddOnBehalfStatusTriggerRequest,
    AddParticipantStatusTriggerRequest,
    AddReportToCaseTriggerRequest,
    CreateCaseTriggerRequest,
    DeferCaseTriggerRequest,
    EngageCaseTriggerRequest,
    LeaveCaseTriggerRequest,
    SetStubSummaryTriggerRequest,
    SyncLogEntryTriggerRequest,
)
from .embargo import (
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
    TerminateEmbargoTriggerRequest,
    WithdrawEmbargoTriggerRequest,
)
from .report import (
    AckReportTriggerRequest,
    InvalidateReportTriggerRequest,
    OfferTriggerRequest,
    RejectReportTriggerRequest,
    SubmitReportTriggerRequest,
    ValidateReportTriggerRequest,
)

__all__ = [
    "AcceptActorRecommendationTriggerRequest",
    "RejectActorRecommendationTriggerRequest",
    "AcceptCaseInviteTriggerRequest",
    "AcceptCaseOwnershipTransferTriggerRequest",
    "AcceptFullCaseInviteTriggerRequest",
    "AcceptEmbargoTriggerRequest",
    "AckReportTriggerRequest",
    "AddNoteToCaseTriggerRequest",
    "AddObjectToCaseTriggerRequest",
    "AddOnBehalfStatusTriggerRequest",
    "AddParticipantStatusTriggerRequest",
    "AddReportToCaseTriggerRequest",
    "CaseTriggerRequest",
    "CreateCaseTriggerRequest",
    "DeferCaseTriggerRequest",
    "RejectFullCaseInviteTriggerRequest",
    "TentativeRejectFullCaseInviteTriggerRequest",
    "EngageCaseTriggerRequest",
    "InvalidateReportTriggerRequest",
    "InviteActorToCaseTriggerRequest",
    "LeaveCaseTriggerRequest",
    "OfferCaseOwnershipTransferTriggerRequest",
    "OfferCaseParticipantRoleTriggerRequest",
    "OfferTriggerRequest",
    "ProposeEmbargoRevisionTriggerRequest",
    "ProposeEmbargoTriggerRequest",
    "RejectCaseInviteTriggerRequest",
    "RejectCaseOwnershipTransferTriggerRequest",
    "RejectEmbargoTriggerRequest",
    "RejectReportTriggerRequest",
    "ResultT_co",
    "SetStubSummaryTriggerRequest",
    "SubmitReportTriggerRequest",
    "SuggestActorToCaseTriggerRequest",
    "SyncLogEntryTriggerRequest",
    "TerminateEmbargoTriggerRequest",
    "WithdrawEmbargoTriggerRequest",
    "TriggerRequest",
    "ValidateReportTriggerRequest",
    "WithdrawCaseOwnershipTransferTriggerRequest",
    "result_type_of",
]
