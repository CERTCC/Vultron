"""Actor- and role-domain trigger registry rows."""

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

from vultron.core.models.use_case_result import (
    ActivityResult,
    RoleOfferResult,
)
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
from vultron.core.use_cases.triggers.requests import (
    AcceptActorRecommendationTriggerRequest,
    AcceptCaseInviteTriggerRequest,
    AcceptCaseOwnershipTransferTriggerRequest,
    InviteActorToCaseTriggerRequest,
    OfferCaseOwnershipTransferTriggerRequest,
    OfferCaseParticipantRoleTriggerRequest,
    RejectCaseInviteTriggerRequest,
    SuggestActorToCaseTriggerRequest,
)
from vultron.trigger_registry._entry import (
    GENERAL_TRIGGER_SPECS,
    TriggerEntry,
    TriggerExposure,
)

_PARTICIPANT = GENERAL_TRIGGER_SPECS + ("TRIG-02-005",)
_ROLE = GENERAL_TRIGGER_SPECS + ("TRIG-02-007",)

ENTRIES: list[TriggerEntry] = [
    TriggerEntry(
        verb="suggest-actor-to-case",
        request_model=SuggestActorToCaseTriggerRequest,
        use_case_class=SvcSuggestActorToCaseUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_PARTICIPANT,
    ),
    TriggerEntry(
        verb="accept-case-invite",
        request_model=AcceptCaseInviteTriggerRequest,
        use_case_class=SvcAcceptCaseInviteUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_PARTICIPANT,
    ),
    TriggerEntry(
        verb="reject-case-invite",
        request_model=RejectCaseInviteTriggerRequest,
        use_case_class=SvcRejectCaseInviteUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_PARTICIPANT,
    ),
    TriggerEntry(
        verb="invite-actor-to-case",
        request_model=InviteActorToCaseTriggerRequest,
        use_case_class=SvcInviteActorToCaseUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_PARTICIPANT,
    ),
    TriggerEntry(
        verb="accept-actor-recommendation",
        request_model=AcceptActorRecommendationTriggerRequest,
        use_case_class=SvcAcceptActorRecommendationUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_PARTICIPANT + ("CM-16-006",),
    ),
    # The one verb not backed by ``SvcBTTriggerBase`` (ADR-0110 § Named
    # exceptions): its body carries no ``emitting_actor_id``.
    TriggerEntry(
        verb="offer-case-participant-role",
        request_model=OfferCaseParticipantRoleTriggerRequest,
        use_case_class=SvcOfferCaseParticipantRoleUseCase,
        result_type=RoleOfferResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=False,
        spec_ids=_ROLE,
    ),
    TriggerEntry(
        verb="offer-case-ownership-transfer",
        request_model=OfferCaseOwnershipTransferTriggerRequest,
        use_case_class=SvcOfferCaseOwnershipTransferUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_ROLE + ("TRIG-11-001",),
    ),
    TriggerEntry(
        verb="accept-case-ownership-transfer",
        request_model=AcceptCaseOwnershipTransferTriggerRequest,
        use_case_class=SvcAcceptCaseOwnershipTransferUseCase,
        result_type=ActivityResult,
        exposure=TriggerExposure.GENERAL_PURPOSE,
        bt_backed=True,
        spec_ids=_ROLE + ("TRIG-11-002",),
    ),
]
