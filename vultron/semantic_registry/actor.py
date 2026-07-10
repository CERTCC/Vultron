"""Actor and case-membership semantic registry entries.

Covers actor suggestions, case manager role negotiation, ownership transfer,
invite/accept/reject to case, and vulnerability case announcements.
"""

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

from vultron.core.models.events.actor import (
    AcceptActorRecommendationReceivedEvent,
    AcceptCaseManagerRoleReceivedEvent,
    AcceptCaseOwnershipTransferReceivedEvent,
    AcceptInviteActorToCaseReceivedEvent,
    AcceptSuggestActorToCaseReceivedEvent,
    AnnounceVulnerabilityCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    OfferActorToCaseReceivedEvent,
    OfferCaseManagerRoleReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    RejectActorRecommendationReceivedEvent,
    RejectCaseManagerRoleReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
    RejectSuggestActorToCaseReceivedEvent,
    SuggestActorToCaseReceivedEvent,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.use_cases.received.actor import (
    AcceptActorRecommendationReceivedUseCase,
    AcceptCaseManagerRoleReceivedUseCase,
    AcceptCaseOwnershipTransferReceivedUseCase,
    AcceptInviteActorToCaseReceivedUseCase,
    AcceptSuggestActorToCaseReceivedUseCase,
    AnnounceVulnerabilityCaseReceivedUseCase,
    InviteActorToCaseReceivedUseCase,
    OfferActorToCaseReceivedUseCase,
    OfferCaseManagerRoleReceivedUseCase,
    OfferCaseOwnershipTransferReceivedUseCase,
    RejectActorRecommendationReceivedUseCase,
    RejectCaseManagerRoleReceivedUseCase,
    RejectCaseOwnershipTransferReceivedUseCase,
    RejectInviteActorToCaseReceivedUseCase,
    RejectSuggestActorToCaseReceivedUseCase,
    SuggestActorToCaseReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.extractor import (
    AcceptActorRecommendationPattern,
    AcceptCaseManagerRolePattern,
    AcceptCaseOwnershipTransferActivityPattern,
    AcceptInviteActorToCasePattern,
    AcceptSuggestActorToCasePattern,
    AnnounceVulnerabilityCasePattern,
    InviteActorToCasePattern,
    OfferActorToCasePattern,
    OfferCaseManagerRolePattern,
    OfferCaseOwnershipTransferActivityPattern,
    RejectActorRecommendationPattern,
    RejectCaseManagerRolePattern,
    RejectCaseOwnershipTransferActivityPattern,
    RejectInviteActorToCasePattern,
    RejectSuggestActorToCasePattern,
    SuggestActorToCasePattern,
)
from vultron.wire.as2.vocab.activities.actor import (
    _AcceptActorRecommendationActivity,
    _AcceptCaseParticipantOfferActivity,
    _OfferCaseParticipantActivity,
    _RecommendActorActivity,
    _RejectActorRecommendationActivity,
    _RejectCaseParticipantOfferActivity,
)
from vultron.wire.as2.vocab.activities.case import (
    _AcceptCaseManagerRoleActivity,
    _AcceptCaseOwnershipTransferActivity,
    _AnnounceVulnerabilityCaseActivity,
    _OfferCaseManagerRoleActivity,
    _OfferCaseOwnershipTransferActivity,
    _RejectCaseManagerRoleActivity,
    _RejectCaseOwnershipTransferActivity,
    _RmAcceptInviteToCaseActivity,
    _RmInviteToCaseActivity,
    _RmRejectInviteToCaseActivity,
)

ENTRIES: list[SemanticEntry] = [
    SemanticEntry(
        semantics=MessageSemantics.SUGGEST_ACTOR_TO_CASE,
        pattern=SuggestActorToCasePattern,
        event_class=SuggestActorToCaseReceivedEvent,
        use_case_class=SuggestActorToCaseReceivedUseCase,
        wire_activity_class=_RecommendActorActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE,
        pattern=AcceptSuggestActorToCasePattern,
        event_class=AcceptSuggestActorToCaseReceivedEvent,
        use_case_class=AcceptSuggestActorToCaseReceivedUseCase,
        wire_activity_class=_AcceptActorRecommendationActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE,
        pattern=RejectSuggestActorToCasePattern,
        event_class=RejectSuggestActorToCaseReceivedEvent,
        use_case_class=RejectSuggestActorToCaseReceivedUseCase,
        wire_activity_class=_RejectActorRecommendationActivity,
    ),
    # CaseActor-routed ADR-0026 flow (CM-16)
    SemanticEntry(
        semantics=MessageSemantics.OFFER_ACTOR_TO_CASE,
        pattern=OfferActorToCasePattern,
        event_class=OfferActorToCaseReceivedEvent,
        use_case_class=OfferActorToCaseReceivedUseCase,
        wire_activity_class=_OfferCaseParticipantActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_ACTOR_RECOMMENDATION,
        pattern=AcceptActorRecommendationPattern,
        event_class=AcceptActorRecommendationReceivedEvent,
        use_case_class=AcceptActorRecommendationReceivedUseCase,
        wire_activity_class=_AcceptCaseParticipantOfferActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_ACTOR_RECOMMENDATION,
        pattern=RejectActorRecommendationPattern,
        event_class=RejectActorRecommendationReceivedEvent,
        use_case_class=RejectActorRecommendationReceivedUseCase,
        wire_activity_class=_RejectCaseParticipantOfferActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.OFFER_CASE_MANAGER_ROLE,
        pattern=OfferCaseManagerRolePattern,
        event_class=OfferCaseManagerRoleReceivedEvent,
        use_case_class=OfferCaseManagerRoleReceivedUseCase,
        wire_activity_class=_OfferCaseManagerRoleActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_CASE_MANAGER_ROLE,
        pattern=AcceptCaseManagerRolePattern,
        event_class=AcceptCaseManagerRoleReceivedEvent,
        use_case_class=AcceptCaseManagerRoleReceivedUseCase,
        wire_activity_class=_AcceptCaseManagerRoleActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_CASE_MANAGER_ROLE,
        pattern=RejectCaseManagerRolePattern,
        event_class=RejectCaseManagerRoleReceivedEvent,
        use_case_class=RejectCaseManagerRoleReceivedUseCase,
        wire_activity_class=_RejectCaseManagerRoleActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER,
        pattern=OfferCaseOwnershipTransferActivityPattern,
        event_class=OfferCaseOwnershipTransferReceivedEvent,
        use_case_class=OfferCaseOwnershipTransferReceivedUseCase,
        wire_activity_class=_OfferCaseOwnershipTransferActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER,
        pattern=AcceptCaseOwnershipTransferActivityPattern,
        event_class=AcceptCaseOwnershipTransferReceivedEvent,
        use_case_class=AcceptCaseOwnershipTransferReceivedUseCase,
        wire_activity_class=_AcceptCaseOwnershipTransferActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER,
        pattern=RejectCaseOwnershipTransferActivityPattern,
        event_class=RejectCaseOwnershipTransferReceivedEvent,
        use_case_class=RejectCaseOwnershipTransferReceivedUseCase,
        wire_activity_class=_RejectCaseOwnershipTransferActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.INVITE_ACTOR_TO_CASE,
        pattern=InviteActorToCasePattern,
        event_class=InviteActorToCaseReceivedEvent,
        use_case_class=InviteActorToCaseReceivedUseCase,
        wire_activity_class=_RmInviteToCaseActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
        pattern=AcceptInviteActorToCasePattern,
        event_class=AcceptInviteActorToCaseReceivedEvent,
        use_case_class=AcceptInviteActorToCaseReceivedUseCase,
        wire_activity_class=_RmAcceptInviteToCaseActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE,
        pattern=RejectInviteActorToCasePattern,
        event_class=RejectInviteActorToCaseReceivedEvent,
        use_case_class=RejectInviteActorToCaseReceivedUseCase,
        wire_activity_class=_RmRejectInviteToCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ANNOUNCE_VULNERABILITY_CASE,
        pattern=AnnounceVulnerabilityCasePattern,
        event_class=AnnounceVulnerabilityCaseReceivedEvent,
        use_case_class=AnnounceVulnerabilityCaseReceivedUseCase,
        wire_activity_class=_AnnounceVulnerabilityCaseActivity,
        include_activity=True,
    ),
]
