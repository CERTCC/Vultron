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

from vultron.core.behaviors.sender_entitlement import (
    AddresseeSide,
    SenderEntitlementKind,
)
from vultron.core.models.events.actor import (
    AcceptActorRecommendationReceivedEvent,
    AcceptCaseOwnershipTransferReceivedEvent,
    AcceptCaseParticipantRoleReceivedEvent,
    AcceptInviteActorToCaseReceivedEvent,
    AcceptInviteActorToFullCaseReceivedEvent,
    AcceptOfferCaseParticipantReceivedEvent,
    AnnounceVulnerabilityCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    InviteActorToFullCaseReceivedEvent,
    OfferActorToCaseReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    OfferCaseParticipantReceivedEvent,
    OfferCaseParticipantRoleReceivedEvent,
    RejectActorRecommendationReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    RejectCaseParticipantRoleReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
    RejectInviteActorToFullCaseReceivedEvent,
    RejectOfferCaseParticipantReceivedEvent,
    TentativeRejectInviteActorToFullCaseReceivedEvent,
    UndoCaseOwnershipTransferReceivedEvent,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.use_cases.received.actor import (
    AcceptActorRecommendationReceivedUseCase,
    AcceptCaseOwnershipTransferReceivedUseCase,
    AcceptCaseParticipantRoleReceivedUseCase,
    AcceptInviteActorToCaseReceivedUseCase,
    AcceptInviteActorToFullCaseReceivedUseCase,
    AcceptOfferCaseParticipantReceivedUseCase,
    AnnounceVulnerabilityCaseReceivedUseCase,
    InviteActorToCaseReceivedUseCase,
    InviteActorToFullCaseReceivedUseCase,
    OfferActorToCaseReceivedUseCase,
    OfferCaseOwnershipTransferReceivedUseCase,
    OfferCaseParticipantReceivedUseCase,
    OfferCaseParticipantRoleReceivedUseCase,
    RejectActorRecommendationReceivedUseCase,
    RejectCaseOwnershipTransferReceivedUseCase,
    RejectCaseParticipantRoleReceivedUseCase,
    RejectInviteActorToCaseReceivedUseCase,
    RejectInviteActorToFullCaseReceivedUseCase,
    RejectOfferCaseParticipantReceivedUseCase,
    TentativeRejectInviteActorToFullCaseReceivedUseCase,
    UndoCaseOwnershipTransferReceivedUseCase,
)
from vultron.enums.roles import CVDRole
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
    AcceptCaseOwnershipTransferActivityPattern,
    AcceptCaseParticipantRolePattern,
    AcceptInviteActorToCasePattern,
    AcceptInviteActorToFullCasePattern,
    AnnounceVulnerabilityCasePattern,
    InviteActorToCasePattern,
    InviteActorToFullCasePattern,
    OfferActorToCasePattern,
    OfferCaseOwnershipTransferActivityPattern,
    OfferCaseParticipantRolePattern,
    RejectActorRecommendationPattern,
    RejectCaseOwnershipTransferActivityPattern,
    RejectCaseParticipantRolePattern,
    RejectInviteActorToCasePattern,
    RejectInviteActorToFullCasePattern,
    TentativeRejectInviteActorToFullCasePattern,
    UndoCaseOwnershipTransferActivityPattern,
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
from vultron.wire.as2.vocab.activities.case import (
    _AcceptCaseOwnershipTransferActivity,
    _AcceptCaseParticipantRoleActivity,
    _AnnounceVulnerabilityCaseActivity,
    _OfferCaseOwnershipTransferActivity,
    _OfferCaseParticipantRoleActivity,
    _RejectCaseOwnershipTransferActivity,
    _RejectCaseParticipantRoleActivity,
    _RmAcceptFullCaseInviteActivity,
    _RmAcceptInviteToCaseActivity,
    _RmInviteToCaseActivity,
    _RmInviteToFullCaseActivity,
    _RmRejectFullCaseInviteActivity,
    _RmRejectInviteToCaseActivity,
    _RmTentativeRejectFullCaseInviteActivity,
    _UndoCaseOwnershipTransferActivity,
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
                    "Recommends an actor to the Case Manager for the case "
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
                heading="Ask the Case Manager to invite an actor",
                description=(
                    "Asks the Case Manager to invite the actor named by the "
                    "object to the case named by the target, with the roles "
                    "in `suggestedRoles`. For an actor with no record on the "
                    "case, or an invitee that has not answered, the Case "
                    "Manager answers with the Stub Invite to that actor, not "
                    "with an offer to the Case Owner."
                ),
                example="request_invite_actor_to_case",
                distinguisher=SenderStanding(
                    kind=SenderEntitlementKind.CASE_OWNER, holds=True
                ),
                howto=HowToGuide.INVITE_ACTOR,
                usual_senders=(CVDRole.CASE_OWNER,),
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
                    "the Case Manager presents a suggested actor to the Case "
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
                    "Accepts the proposed participant record. The Case Manager"
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
                    "Rejects the proposed participant record. The Case Manager"
                    " tells the recommender."
                ),
                example="reject_case_participant_offer",
                howto=HowToGuide.SUGGEST_ACTOR,
                shorthand=ProtocolShorthand.GI,
            ),
        ),
        page=MessagePage.GENERAL,
    ),
    # Recommender inbox: the CASE_MANAGER's answer to its Offer(Actor, Case)
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
                    "the Case Manager tells a recommender that the actor it "
                    "suggested will be invited"
                ),
                anchor="accept-actor-recommendation",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Accept actor recommendation",
                description=(
                    "Accepts the recommender's suggestion, with `inReplyTo` "
                    "naming it. The Case Manager sends it once the Case Owner"
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
                    "the Case Manager tells a recommender that the Case "
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
    SemanticEntry(
        semantics=MessageSemantics.OFFER_CASE_PARTICIPANT_ROLE,
        pattern=OfferCaseParticipantRolePattern,
        event_class=OfferCaseParticipantRoleReceivedEvent,
        use_case_class=OfferCaseParticipantRoleReceivedUseCase,
        phrase="{actor} offered {object} role to {target} in the case",
        wire_activity_class=_OfferCaseParticipantRoleActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Owner offers a CVD role on the case to another "
                    "participant"
                ),
                anchor="offer-case-participant-role",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Offer case participant role",
                description=(
                    "Offers one role on the case to the participant named by"
                    " the target. The Case Manager records the offer and"
                    " forwards it to that participant."
                ),
                example="offer_case_participant_role",
                howto=HowToGuide.ROLE_DELEGATION,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_CASE_PARTICIPANT_ROLE,
        pattern=AcceptCaseParticipantRolePattern,
        event_class=AcceptCaseParticipantRoleReceivedEvent,
        use_case_class=AcceptCaseParticipantRoleReceivedUseCase,
        phrase="{actor} accepted the role offer",
        wire_activity_class=_AcceptCaseParticipantRoleActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="a participant accepts a role offered to it on the case",
                anchor="accept-case-participant-role",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Accept case participant role",
                description=(
                    "Accepts the offered role. The participant holds the role"
                    " once the Case Manager records the acceptance."
                ),
                example="accept_case_participant_role",
                howto=HowToGuide.ROLE_DELEGATION,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_CASE_PARTICIPANT_ROLE,
        pattern=RejectCaseParticipantRolePattern,
        event_class=RejectCaseParticipantRoleReceivedEvent,
        use_case_class=RejectCaseParticipantRoleReceivedUseCase,
        phrase="{actor} declined the role offer",
        wire_activity_class=_RejectCaseParticipantRoleActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="a participant declines a role offered to it on the case",
                anchor="reject-case-participant-role",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Reject case participant role",
                description=(
                    "Declines the offered role. The roster does not change."
                ),
                example="reject_case_participant_role",
                howto=HowToGuide.ROLE_DELEGATION,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER,
        pattern=OfferCaseOwnershipTransferActivityPattern,
        event_class=OfferCaseOwnershipTransferReceivedEvent,
        use_case_class=OfferCaseOwnershipTransferReceivedUseCase,
        phrase="{actor} offered {object} case ownership",
        wire_activity_class=_OfferCaseOwnershipTransferActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Owner offers to transfer ownership of the case "
                    "to another actor"
                ),
                anchor="offer-case-ownership-transfer",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Offer case ownership transfer",
                description=(
                    "Offers the case to the actor named by the target, for "
                    "example from a Reporter to a Coordinator, optionally "
                    "with an `endTime` after which the CASE_MANAGER refuses "
                    "an answer and records the offer as expired."
                ),
                example="offer_case_ownership_transfer",
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER,
        pattern=AcceptCaseOwnershipTransferActivityPattern,
        event_class=AcceptCaseOwnershipTransferReceivedEvent,
        use_case_class=AcceptCaseOwnershipTransferReceivedUseCase,
        phrase="{actor} accepted case ownership",
        wire_activity_class=_AcceptCaseOwnershipTransferActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="an actor accepts an offer of case ownership",
                anchor="accept-case-ownership-transfer",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Accept case ownership transfer",
                description="Accepts the ownership transfer offer.",
                example="accept_case_ownership_transfer",
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER,
        pattern=RejectCaseOwnershipTransferActivityPattern,
        event_class=RejectCaseOwnershipTransferReceivedEvent,
        use_case_class=RejectCaseOwnershipTransferReceivedUseCase,
        phrase="{actor} declined case ownership",
        wire_activity_class=_RejectCaseOwnershipTransferActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="an actor declines an offer of case ownership",
                anchor="reject-case-ownership-transfer",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Reject case ownership transfer",
                description=(
                    "Declines the ownership transfer offer. The current Case "
                    "Owner keeps the case."
                ),
                example="reject_case_ownership_transfer",
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.UNDO_CASE_OWNERSHIP_TRANSFER,
        pattern=UndoCaseOwnershipTransferActivityPattern,
        event_class=UndoCaseOwnershipTransferReceivedEvent,
        use_case_class=UndoCaseOwnershipTransferReceivedUseCase,
        phrase="{actor} withdrew the case ownership offer",
        wire_activity_class=_UndoCaseOwnershipTransferActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Owner withdraws an open offer of case ownership"
                ),
                anchor="withdraw-case-ownership-transfer",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Withdraw case ownership transfer",
                description=(
                    "Withdraws the ownership transfer offer before it is "
                    "answered. The current Case Owner keeps the case."
                ),
                example="undo_case_ownership_transfer",
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.INVITE_ACTOR_TO_CASE,
        pattern=InviteActorToCasePattern,
        event_class=InviteActorToCaseReceivedEvent,
        use_case_class=InviteActorToCaseReceivedUseCase,
        phrase="{actor} invited {object} to the case",
        wire_activity_class=_RmInviteToCaseActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="the Case Manager invites an actor to join the case",
                anchor="invite-actor-to-case",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Invite actor to case",
                description=(
                    "Sends a Stub Invite carrying the case stub and the "
                    "embargo terms the invitee would agree to."
                ),
                example="rm_invite_to_case",
                howto=HowToGuide.INVITE_ACTOR,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
        pattern=AcceptInviteActorToCasePattern,
        event_class=AcceptInviteActorToCaseReceivedEvent,
        use_case_class=AcceptInviteActorToCaseReceivedUseCase,
        phrase="{actor} accepted the case invitation",
        wire_activity_class=_RmAcceptInviteToCaseActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="an invited actor agrees to join the case",
                anchor="accept-invite-to-case",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Accept invite to case",
                description=(
                    "Accepts the Stub Invite. The actor joins the case at RM "
                    "Received."
                ),
                example="accept_invite_to_case",
                howto=HowToGuide.INVITE_ACTOR,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE,
        pattern=RejectInviteActorToCasePattern,
        event_class=RejectInviteActorToCaseReceivedEvent,
        use_case_class=RejectInviteActorToCaseReceivedUseCase,
        phrase="{actor} declined the case invitation",
        wire_activity_class=_RmRejectInviteToCaseActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="an invited actor declines to join the case",
                anchor="reject-invite-to-case",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Reject invite to case",
                description=(
                    "Rejects the Stub Invite, which closes the invitee's "
                    "participant record."
                ),
                example="reject_invite_to_case",
                howto=HowToGuide.INVITE_ACTOR,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.INVITE_ACTOR_TO_FULL_CASE,
        pattern=InviteActorToFullCasePattern,
        event_class=InviteActorToFullCaseReceivedEvent,
        use_case_class=InviteActorToFullCaseReceivedUseCase,
        phrase="{actor} invited {object} to judge the case",
        wire_activity_class=_RmInviteToFullCaseActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Manager has replayed the case ledger to a newly "
                    "joined Participant"
                ),
                anchor="invite-actor-to-full-case",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Send Full-Case Invite",
                description=(
                    "Sends the Full-Case Invite, which asks the Participant to"
                    " judge the case. It carries the Case Manager's ledger "
                    "position as the floor the reply must reach."
                ),
                example="invite_to_full_case",
                howto=HowToGuide.MANAGE_PARTICIPANTS,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_INVITE_ACTOR_TO_FULL_CASE,
        pattern=AcceptInviteActorToFullCasePattern,
        event_class=AcceptInviteActorToFullCaseReceivedEvent,
        use_case_class=AcceptInviteActorToFullCaseReceivedUseCase,
        phrase="{actor} judged the case valid",
        wire_activity_class=_RmAcceptFullCaseInviteActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "a Participant asked by a Full-Case Invite judges the case"
                    " valid"
                ),
                anchor="accept-full-case-invite",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Accept Full-Case Invite",
                description=(
                    "Accepts the Full-Case Invite, which records RM Valid. It "
                    "carries the sender's own ledger position."
                ),
                example="accept_full_case_invite",
                howto=HowToGuide.MANAGE_PARTICIPANTS,
                shorthand=ProtocolShorthand.RV,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE,
        pattern=TentativeRejectInviteActorToFullCasePattern,
        event_class=TentativeRejectInviteActorToFullCaseReceivedEvent,
        use_case_class=TentativeRejectInviteActorToFullCaseReceivedUseCase,
        phrase="{actor} judged the case invalid",
        wire_activity_class=_RmTentativeRejectFullCaseInviteActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "a Participant asked by a Full-Case Invite judges the case"
                    " invalid"
                ),
                anchor="tentatively-reject-full-case-invite",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Tentatively reject Full-Case Invite",
                description=(
                    "Tentatively rejects the Full-Case Invite, which records "
                    "RM Invalid. It carries the sender's own ledger position."
                ),
                example="tentative_reject_full_case_invite",
                howto=HowToGuide.MANAGE_PARTICIPANTS,
                shorthand=ProtocolShorthand.RI,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_INVITE_ACTOR_TO_FULL_CASE,
        pattern=RejectInviteActorToFullCasePattern,
        event_class=RejectInviteActorToFullCaseReceivedEvent,
        use_case_class=RejectInviteActorToFullCaseReceivedUseCase,
        phrase="{actor} closed the case",
        wire_activity_class=_RmRejectFullCaseInviteActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "a Participant asked by a Full-Case Invite closes the case"
                ),
                anchor="reject-full-case-invite",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Reject Full-Case Invite",
                description=(
                    "Rejects the Full-Case Invite, which records RM Closed. It"
                    " carries the sender's own ledger position."
                ),
                example="reject_full_case_invite",
                howto=HowToGuide.MANAGE_PARTICIPANTS,
                shorthand=ProtocolShorthand.RC,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ANNOUNCE_VULNERABILITY_CASE,
        pattern=AnnounceVulnerabilityCasePattern,
        event_class=AnnounceVulnerabilityCaseReceivedEvent,
        use_case_class=AnnounceVulnerabilityCaseReceivedUseCase,
        phrase="{actor} announced the case",
        wire_activity_class=_AnnounceVulnerabilityCaseActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Manager has admitted a new Participant to the "
                    "case"
                ),
                anchor="announce-vulnerability-case",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Announce vulnerability case",
                description=(
                    "Sends the full case to the newly admitted Participant "
                    "once its acceptance clears the embargo consent checks."
                ),
                example="announce_case",
                howto=HowToGuide.INVITE_ACTOR,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
]
