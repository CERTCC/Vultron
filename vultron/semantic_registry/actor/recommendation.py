"""Actor recommendation and case-participant offer registry entries (CM-16)."""

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

from vultron.core.behaviors.sender_entitlement import (
    AddresseeSide,
    SenderEntitlementKind,
)
from vultron.core.models.events.actor import (
    AcceptActorRecommendationReceivedEvent,
    AcceptOfferCaseParticipantReceivedEvent,
    OfferActorToCaseReceivedEvent,
    OfferCaseParticipantReceivedEvent,
    RejectActorRecommendationReceivedEvent,
    RejectOfferCaseParticipantReceivedEvent,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.use_cases.received.actor import (
    AcceptActorRecommendationReceivedUseCase,
    AcceptOfferCaseParticipantReceivedUseCase,
    OfferActorToCaseReceivedUseCase,
    OfferCaseParticipantReceivedUseCase,
    RejectActorRecommendationReceivedUseCase,
    RejectOfferCaseParticipantReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    HowToGuide,
    MessagePage,
    Occasion,
    ProtocolShorthand,
    SenderStanding,
)
from vultron.wire.as2.extractor import (
    AcceptActorRecommendationPattern,
    OfferActorToCasePattern,
    RejectActorRecommendationPattern,
)
from vultron.wire.as2.extractor._instances import (
    AcceptSuggestActorToCasePattern,
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
        occasions=(
            Occasion(
                when=(
                    "a Participant suggests an actor that the case should "
                    "include"
                ),
                anchor="suggest-actor-to-case",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Suggest actor to case",
                description=(
                    "Recommends an actor to the CASE_MANAGER for the case "
                    "named by the target."
                ),
                example="recommend_actor",
                distinguisher=SenderStanding(
                    kind=SenderEntitlementKind.CASE_OWNER, holds=False
                ),
                howto=HowToGuide.SUGGEST_ACTOR,
                shorthand=ProtocolShorthand.GI,
            ),
            Occasion(
                when=("the Case Owner decides to invite an actor to the case"),
                anchor="request-invite-actor-to-case",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Ask the CASE_MANAGER to invite an actor",
                description=(
                    "Asks the CASE_MANAGER to invite the actor named by the "
                    "object to the case named by the target, with the roles "
                    "in `suggestedRoles`. For an actor with no record on the "
                    "case, or an invitee that has not answered, the "
                    "CASE_MANAGER answers with the Stub Invite to that actor, "
                    "not with an offer to the Case Owner."
                ),
                example="request_invite_actor_to_case",
                distinguisher=SenderStanding(
                    kind=SenderEntitlementKind.CASE_OWNER, holds=True
                ),
                howto=HowToGuide.INVITE_ACTOR,
            ),
        ),
        page=MessagePage.GENERAL,
    ),
    # Case Owner inbox: CaseActor's Offer(CaseParticipant) arrives here (CM-16-003/CM-16-004)
    SemanticEntry(
        semantics=MessageSemantics.OFFER_CASE_PARTICIPANT,
        pattern=OfferActorToCasePattern,
        event_class=OfferCaseParticipantReceivedEvent,
        use_case_class=OfferCaseParticipantReceivedUseCase,
        phrase="{actor} offered {object} case participation",
        wire_activity_class=_OfferCaseParticipantActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the CASE_MANAGER presents a suggested actor to the Case "
                    "Owner"
                ),
                anchor="offer-case-participant",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Offer case participant",
                description=(
                    "Forwards the recommendation as a proposed participant "
                    "record, carrying the original recommendation's ID and the"
                    " default roles it assigned."
                ),
                example="offer_case_participant",
                howto=HowToGuide.SUGGEST_ACTOR,
                shorthand=ProtocolShorthand.GI,
            ),
        ),
        page=MessagePage.GENERAL,
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
        occasions=(
            Occasion(
                when="the Case Owner approves a suggested actor",
                anchor="accept-case-participant-offer",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Accept case participant offer",
                description=(
                    "Accepts the proposed participant record. The CASE_MANAGER"
                    " then invites the suggested actor."
                ),
                example="accept_case_participant_offer",
                howto=HowToGuide.SUGGEST_ACTOR,
                shorthand=ProtocolShorthand.GI,
            ),
        ),
        page=MessagePage.GENERAL,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT,
        pattern=RejectActorRecommendationPattern,
        event_class=RejectOfferCaseParticipantReceivedEvent,
        use_case_class=RejectOfferCaseParticipantReceivedUseCase,
        phrase="{actor} declined case participation",
        wire_activity_class=_RejectCaseParticipantOfferActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="the Case Owner declines a suggested actor",
                anchor="reject-case-participant-offer",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Reject case participant offer",
                description=(
                    "Rejects the proposed participant record. The CASE_MANAGER"
                    " tells the recommender."
                ),
                example="reject_case_participant_offer",
                howto=HowToGuide.SUGGEST_ACTOR,
                shorthand=ProtocolShorthand.GI,
            ),
        ),
        page=MessagePage.GENERAL,
    ),
    # Recommender inbox: the CASE_MANAGER's answer to its Offer(Actor)[target=VulnerabilityCase]
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_ACTOR_RECOMMENDATION,
        pattern=AcceptSuggestActorToCasePattern,
        event_class=AcceptActorRecommendationReceivedEvent,
        use_case_class=AcceptActorRecommendationReceivedUseCase,
        phrase="{actor} accepted recommendation {object} for the case",
        wire_activity_class=_AcceptActorRecommendationActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the CASE_MANAGER tells a recommender that the actor it "
                    "suggested will be invited"
                ),
                anchor="accept-actor-recommendation",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Accept actor recommendation",
                description=(
                    "Accepts the recommender's suggestion, with `inReplyTo` "
                    "naming it. The CASE_MANAGER sends it once the Case Owner"
                    " approves, or at once when the suggested actor is "
                    "already invited or has joined."
                ),
                example="accept_actor_recommendation",
                howto=HowToGuide.SUGGEST_ACTOR,
                shorthand=ProtocolShorthand.GI,
            ),
        ),
        page=MessagePage.GENERAL,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_ACTOR_RECOMMENDATION,
        pattern=RejectSuggestActorToCasePattern,
        event_class=RejectActorRecommendationReceivedEvent,
        use_case_class=RejectActorRecommendationReceivedUseCase,
        phrase="{actor} declined recommendation {object} for the case",
        wire_activity_class=_RejectActorRecommendationActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the CASE_MANAGER tells a recommender that the Case "
                    "Owner declined the actor it suggested"
                ),
                anchor="reject-actor-recommendation",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Reject actor recommendation",
                description=(
                    "Declines the recommender's suggestion, with `inReplyTo`"
                    " naming it. The suggested actor is not invited."
                ),
                example="reject_actor_recommendation",
                howto=HowToGuide.SUGGEST_ACTOR,
                shorthand=ProtocolShorthand.GI,
            ),
        ),
        page=MessagePage.GENERAL,
    ),
]
