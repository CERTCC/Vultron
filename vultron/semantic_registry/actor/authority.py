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
    RejectCaseOwnershipTransferActivityPattern,
    RejectCaseParticipantRolePattern,
    UndoCaseOwnershipTransferActivityPattern,
)
from vultron.wire.as2.vocab.activities.case.ownership import (
    _AcceptCaseOwnershipTransferActivity,
    _OfferCaseOwnershipTransferActivity,
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
    SemanticEntry(
        semantics=MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER,
        pattern=OfferCaseOwnershipTransferActivityPattern,
        event_class=OfferCaseOwnershipTransferReceivedEvent,
        use_case_class=OfferCaseOwnershipTransferReceivedUseCase,
        phrase="{actor} offered {target} case ownership",
        wire_activity_class=_OfferCaseOwnershipTransferActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Owner offers ownership of the case to another "
                    "participant"
                ),
                anchor="propose-case-ownership-transfer",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Case Owner offers case ownership",
                description=(
                    "The Case Owner's own Offer, sent to the CASE_MANAGER "
                    "only: the case as the object and the new owner as the "
                    "target, for example from a Reporter to a Coordinator. "
                    "The CASE_MANAGER offers the case only to an active "
                    "participant, so the Case Owner invites any other actor "
                    "first. An optional `endTime` is the deadline to answer: "
                    "after it the CASE_MANAGER refuses an answer, and the "
                    "offer is closed with nothing recorded or sent. The "
                    "CASE_MANAGER records this Offer and makes its own Offer "
                    "to the new owner, which answers that one."
                ),
                example="propose_case_ownership_transfer",
            ),
            Occasion(
                when=(
                    "the CASE_MANAGER offers the case to the actor the Case "
                    "Owner named"
                ),
                anchor="offer-case-ownership-transfer",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Offer case ownership transfer",
                description=(
                    "Offers the case to the actor named by the target, on "
                    "the Case Owner's behalf: `attributedTo` names the owner "
                    "and `inReplyTo` the owner's own Offer. This is the "
                    "offer the new owner accepts or rejects. It carries the "
                    "owner's `endTime`, if any."
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
                    "the Case Owner withdraws its offer while the "
                    "CASE_MANAGER's offer of case ownership is open"
                ),
                anchor="withdraw-case-ownership-transfer",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Withdraw case ownership transfer",
                description=(
                    "Withdraws the Case Owner's own Offer, and with it the "
                    "CASE_MANAGER's offer, before the offer is answered. The "
                    "current Case Owner keeps the case."
                ),
                example="undo_case_ownership_transfer",
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
]
