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
    AcceptCaseOwnershipTransferReceivedEvent,
    AcceptInviteActorToCaseReceivedEvent,
    AcceptOfferCaseParticipantReceivedEvent,
    AnnounceVulnerabilityCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    OfferActorToCaseReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    OfferCaseParticipantReceivedEvent,
    OfferCaseParticipantRoleReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
    RejectOfferCaseParticipantReceivedEvent,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.use_cases.received.actor import (
    AcceptCaseOwnershipTransferReceivedUseCase,
    AcceptInviteActorToCaseReceivedUseCase,
    AcceptOfferCaseParticipantReceivedUseCase,
    AnnounceVulnerabilityCaseReceivedUseCase,
    InviteActorToCaseReceivedUseCase,
    OfferActorToCaseReceivedUseCase,
    OfferCaseOwnershipTransferReceivedUseCase,
    OfferCaseParticipantReceivedUseCase,
    OfferCaseParticipantRoleReceivedUseCase,
    RejectCaseOwnershipTransferReceivedUseCase,
    RejectInviteActorToCaseReceivedUseCase,
    RejectOfferCaseParticipantReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.extractor import (
    AcceptActorRecommendationPattern,
    AcceptCaseOwnershipTransferActivityPattern,
    AcceptInviteActorToCasePattern,
    AnnounceVulnerabilityCasePattern,
    InviteActorToCasePattern,
    OfferActorToCasePattern,
    OfferCaseOwnershipTransferActivityPattern,
    OfferCaseParticipantRolePattern,
    RejectActorRecommendationPattern,
    RejectCaseOwnershipTransferActivityPattern,
    RejectInviteActorToCasePattern,
)
from vultron.wire.as2.extractor._instances import SuggestActorToCasePattern
from vultron.wire.as2.vocab.activities.actor import (
    _AcceptCaseParticipantOfferActivity,
    _OfferCaseParticipantActivity,
    _RecommendActorActivity,
    _RejectCaseParticipantOfferActivity,
)
from vultron.wire.as2.vocab.activities.case import (
    _AcceptCaseOwnershipTransferActivity,
    _AnnounceVulnerabilityCaseActivity,
    _OfferCaseOwnershipTransferActivity,
    _OfferCaseParticipantRoleActivity,
    _RejectCaseOwnershipTransferActivity,
    _RmAcceptInviteToCaseActivity,
    _RmInviteToCaseActivity,
    _RmRejectInviteToCaseActivity,
)

ENTRIES: list[SemanticEntry] = [
    # CaseActor-routed ADR-0026 flow (CM-16)
    SemanticEntry(
        semantics=MessageSemantics.OFFER_ACTOR_TO_CASE,
        pattern=SuggestActorToCasePattern,
        event_class=OfferActorToCaseReceivedEvent,
        use_case_class=OfferActorToCaseReceivedUseCase,
        phrase="{actor} suggested {object} for the case",
        wire_activity_class=_RecommendActorActivity,
        include_activity=True,
    ),
    # Case Owner inbox: CaseActor's Offer(CaseParticipant) arrives here (CM-16-003/CM-16-004)
    SemanticEntry(
        semantics=MessageSemantics.OFFER_CASE_PARTICIPANT,
        pattern=OfferActorToCasePattern,
        event_class=OfferCaseParticipantReceivedEvent,
        use_case_class=OfferCaseParticipantReceivedUseCase,
        phrase="{actor} offered case participation to {object}",
        wire_activity_class=_OfferCaseParticipantActivity,
        include_activity=True,
    ),
    # CaseActor inbox: Case Owner's Accept/Reject(Offer(CaseParticipant)) arrives here
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT,
        pattern=AcceptActorRecommendationPattern,
        event_class=AcceptOfferCaseParticipantReceivedEvent,
        use_case_class=AcceptOfferCaseParticipantReceivedUseCase,
        phrase="{actor} accepted case participation",
        wire_activity_class=_AcceptCaseParticipantOfferActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT,
        pattern=RejectActorRecommendationPattern,
        event_class=RejectOfferCaseParticipantReceivedEvent,
        use_case_class=RejectOfferCaseParticipantReceivedUseCase,
        phrase="{actor} declined case participation",
        wire_activity_class=_RejectCaseParticipantOfferActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.OFFER_CASE_PARTICIPANT_ROLE,
        pattern=OfferCaseParticipantRolePattern,
        event_class=OfferCaseParticipantRoleReceivedEvent,
        use_case_class=OfferCaseParticipantRoleReceivedUseCase,
        phrase="{actor} offered {object} role to {target} in the case",
        wire_activity_class=_OfferCaseParticipantRoleActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER,
        pattern=OfferCaseOwnershipTransferActivityPattern,
        event_class=OfferCaseOwnershipTransferReceivedEvent,
        use_case_class=OfferCaseOwnershipTransferReceivedUseCase,
        phrase="{actor} offered case ownership to {object}",
        wire_activity_class=_OfferCaseOwnershipTransferActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER,
        pattern=AcceptCaseOwnershipTransferActivityPattern,
        event_class=AcceptCaseOwnershipTransferReceivedEvent,
        use_case_class=AcceptCaseOwnershipTransferReceivedUseCase,
        phrase="{actor} accepted case ownership",
        wire_activity_class=_AcceptCaseOwnershipTransferActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER,
        pattern=RejectCaseOwnershipTransferActivityPattern,
        event_class=RejectCaseOwnershipTransferReceivedEvent,
        use_case_class=RejectCaseOwnershipTransferReceivedUseCase,
        phrase="{actor} declined case ownership",
        wire_activity_class=_RejectCaseOwnershipTransferActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.INVITE_ACTOR_TO_CASE,
        pattern=InviteActorToCasePattern,
        event_class=InviteActorToCaseReceivedEvent,
        use_case_class=InviteActorToCaseReceivedUseCase,
        phrase="{actor} invited {object} to the case",
        wire_activity_class=_RmInviteToCaseActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
        pattern=AcceptInviteActorToCasePattern,
        event_class=AcceptInviteActorToCaseReceivedEvent,
        use_case_class=AcceptInviteActorToCaseReceivedUseCase,
        phrase="{actor} accepted the case invitation",
        wire_activity_class=_RmAcceptInviteToCaseActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE,
        pattern=RejectInviteActorToCasePattern,
        event_class=RejectInviteActorToCaseReceivedEvent,
        use_case_class=RejectInviteActorToCaseReceivedUseCase,
        phrase="{actor} declined the case invitation",
        wire_activity_class=_RmRejectInviteToCaseActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ANNOUNCE_VULNERABILITY_CASE,
        pattern=AnnounceVulnerabilityCasePattern,
        event_class=AnnounceVulnerabilityCaseReceivedEvent,
        use_case_class=AnnounceVulnerabilityCaseReceivedUseCase,
        phrase="{actor} announced the case",
        wire_activity_class=_AnnounceVulnerabilityCaseActivity,
        include_activity=True,
    ),
]
