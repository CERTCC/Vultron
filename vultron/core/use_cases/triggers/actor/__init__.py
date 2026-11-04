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

"""Class-based use cases for actor-level trigger behaviors.

One concern per submodule:

- :mod:`.recommendation` — actor recommendations and case invitations, and
  their answers
- :mod:`.invite_answer` — an invitee's answer to a case invitation
- :mod:`.ownership` — case ownership transfer
- :mod:`.participant_role` — the CASE_MANAGER's participant-role offer

No HTTP framework imports permitted here.
"""

from vultron.core.use_cases.triggers.requests import (
    AcceptActorRecommendationTriggerRequest,
    AcceptCaseInviteTriggerRequest,
    AcceptCaseOwnershipTransferTriggerRequest,
    InviteActorToCaseTriggerRequest,
    OfferCaseOwnershipTransferTriggerRequest,
    OfferCaseParticipantRoleTriggerRequest,
    RejectActorRecommendationTriggerRequest,
    RejectCaseInviteTriggerRequest,
    RejectCaseOwnershipTransferTriggerRequest,
    SuggestActorToCaseTriggerRequest,
    WithdrawCaseOwnershipTransferTriggerRequest,
)

from .invite_answer import (
    SvcAcceptCaseInviteUseCase,
    SvcRejectCaseInviteUseCase,
)
from .ownership import (
    SvcAcceptCaseOwnershipTransferUseCase,
    SvcOfferCaseOwnershipTransferUseCase,
    SvcRejectCaseOwnershipTransferUseCase,
    SvcWithdrawCaseOwnershipTransferUseCase,
)
from .participant_role import (
    SvcOfferCaseParticipantRoleUseCase,
)
from .recommendation import (
    SvcAcceptActorRecommendationUseCase,
    SvcInviteActorToCaseUseCase,
    SvcRejectActorRecommendationUseCase,
    SvcSuggestActorToCaseUseCase,
)

__all__ = [
    "AcceptActorRecommendationTriggerRequest",
    "AcceptCaseInviteTriggerRequest",
    "AcceptCaseOwnershipTransferTriggerRequest",
    "InviteActorToCaseTriggerRequest",
    "OfferCaseOwnershipTransferTriggerRequest",
    "OfferCaseParticipantRoleTriggerRequest",
    "RejectActorRecommendationTriggerRequest",
    "RejectCaseInviteTriggerRequest",
    "RejectCaseOwnershipTransferTriggerRequest",
    "SuggestActorToCaseTriggerRequest",
    "SvcAcceptActorRecommendationUseCase",
    "SvcAcceptCaseInviteUseCase",
    "SvcAcceptCaseOwnershipTransferUseCase",
    "SvcInviteActorToCaseUseCase",
    "SvcOfferCaseOwnershipTransferUseCase",
    "SvcOfferCaseParticipantRoleUseCase",
    "SvcRejectActorRecommendationUseCase",
    "SvcRejectCaseInviteUseCase",
    "SvcRejectCaseOwnershipTransferUseCase",
    "SvcSuggestActorToCaseUseCase",
    "SvcWithdrawCaseOwnershipTransferUseCase",
    "WithdrawCaseOwnershipTransferTriggerRequest",
]
