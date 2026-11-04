"""CASE_MANAGER role negotiation and case ownership transfer registry entries."""

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

from vultron.core.behaviors.sender_entitlement import AddresseeSide
from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    AcceptCaseParticipantRoleReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    OfferCaseParticipantRoleReceivedEvent,
    ProposeCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    RejectCaseParticipantRoleReceivedEvent,
    UndoCaseOwnershipTransferReceivedEvent,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.use_cases.received.actor import (
    AcceptCaseOwnershipTransferReceivedUseCase,
    AcceptCaseParticipantRoleReceivedUseCase,
    OfferCaseOwnershipTransferReceivedUseCase,
    OfferCaseParticipantRoleReceivedUseCase,
    ProposeCaseOwnershipTransferReceivedUseCase,
    RejectCaseOwnershipTransferReceivedUseCase,
    RejectCaseParticipantRoleReceivedUseCase,
    UndoCaseOwnershipTransferReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    HowToGuide,
    MessagePage,
    Occasion,
)
from vultron.wire.as2.extractor import (
    AcceptCaseOwnershipTransferActivityPattern,
    AcceptCaseParticipantRolePattern,
    OfferCaseOwnershipTransferActivityPattern,
    OfferCaseParticipantRolePattern,
    ProposeCaseOwnershipTransferActivityPattern,
    RejectCaseOwnershipTransferActivityPattern,
    RejectCaseParticipantRolePattern,
    UndoCaseOwnershipTransferActivityPattern,
)
from vultron.wire.as2.vocab.activities.case.ownership import (
    _AcceptCaseOwnershipTransferActivity,
    _OfferCaseOwnershipTransferActivity,
    _ProposeCaseOwnershipTransferActivity,
    _RejectCaseOwnershipTransferActivity,
    _UndoCaseOwnershipTransferActivity,
)
from vultron.wire.as2.vocab.activities.case.roles import (
    _AcceptCaseParticipantRoleActivity,
    _OfferCaseParticipantRoleActivity,
    _RejectCaseParticipantRoleActivity,
)

ENTRIES: list[SemanticEntry] = [
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
                    " the target. The CASE_MANAGER records the offer and"
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
                    " once the CASE_MANAGER records the acceptance."
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
    # Before the Offer(VulnerabilityCase) entry: the proposal is an Offer
    # whose object is that Offer, the more specific shape (ADR-0148).
    SemanticEntry(
        semantics=MessageSemantics.PROPOSE_CASE_OWNERSHIP_TRANSFER,
        pattern=ProposeCaseOwnershipTransferActivityPattern,
        event_class=ProposeCaseOwnershipTransferReceivedEvent,
        use_case_class=ProposeCaseOwnershipTransferReceivedUseCase,
        phrase="{actor} proposed an offer of case ownership",
        wire_activity_class=_ProposeCaseOwnershipTransferActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Owner proposes to transfer ownership of the "
                    "case to another participant"
                ),
                anchor="propose-case-ownership-transfer",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Propose case ownership transfer",
                description=(
                    "Asks the CASE_MANAGER to offer the case to another "
                    "participant, for example from a Reporter to a "
                    "Coordinator. The CASE_MANAGER offers the case only to "
                    "an active participant, so the Case Owner invites any "
                    "other actor first. The inner Offer names the case, the "
                    "new owner as its target and, optionally, an `endTime` "
                    "after which the CASE_MANAGER refuses an answer: the "
                    "offer is then closed, with nothing recorded or sent. "
                    "The CASE_MANAGER makes the offer itself."
                ),
                example="propose_case_ownership_transfer",
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
                    "the CASE_MANAGER offers the case to the actor the Case "
                    "Owner proposed"
                ),
                anchor="offer-case-ownership-transfer",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Offer case ownership transfer",
                description=(
                    "Offers the case to the actor named by the target, on "
                    "the Case Owner's behalf: `attributedTo` names the owner. "
                    "This is the one offer of the transfer, the one the new "
                    "owner accepts or rejects. It carries the proposal's "
                    "`endTime`, if any."
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
                    "the Case Owner withdraws its proposal while the offer "
                    "of case ownership is open"
                ),
                anchor="withdraw-case-ownership-transfer",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Withdraw case ownership transfer",
                description=(
                    "Withdraws the proposal, and with it the CASE_MANAGER's "
                    "offer, before the offer is answered. The current Case "
                    "Owner keeps the case."
                ),
                example="undo_case_ownership_transfer",
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
]
