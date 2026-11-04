"""Embargo invitation registry entries: Invite, its answers and its withdrawal."""

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
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
    InviteToEmbargoOnCaseReceivedEvent,
    RejectInviteToEmbargoOnCaseReceivedEvent,
    UndoInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    HowToGuide,
    MessagePage,
    Occasion,
    ProtocolShorthand,
    StateContext,
)
from vultron.wire.as2.extractor import (
    AcceptInviteToEmbargoOnCasePattern,
    InviteToEmbargoOnCasePattern,
    RejectInviteToEmbargoOnCasePattern,
    UndoInviteToEmbargoOnCasePattern,
)
from vultron.wire.as2.vocab.activities.embargo import (
    _EmAcceptEmbargoActivity,
    _EmProposeEmbargoActivity,
    _EmRejectEmbargoActivity,
    _EmUndoEmbargoInviteActivity,
)

ENTRIES: list[SemanticEntry] = [
    SemanticEntry(
        semantics=MessageSemantics.INVITE_TO_EMBARGO_ON_CASE,
        pattern=InviteToEmbargoOnCasePattern,
        event_class=InviteToEmbargoOnCaseReceivedEvent,
        use_case_class=InviteToEmbargoOnCaseReceivedUseCase,
        phrase="{actor} proposed an embargo",
        wire_activity_class=_EmProposeEmbargoActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "a Participant proposes embargo terms for a case with no "
                    "active embargo"
                ),
                anchor="embargo-proposal",
                addressee=AddresseeSide.CASE_MANAGER,
                description=(
                    "Proposes embargo terms, such as an end date and time."
                ),
                example="propose_embargo",
                distinguisher=StateContext(
                    machine=EM,
                    states=(
                        EM.NONE,
                        EM.PROPOSED,
                    ),
                ),
                howto=HowToGuide.ESTABLISH_EMBARGO,
                shorthand=ProtocolShorthand.EP,
            ),
            Occasion(
                when=(
                    "a Participant proposes revised terms for the active "
                    "embargo"
                ),
                anchor="embargo-revision-proposal",
                addressee=AddresseeSide.CASE_MANAGER,
                description=(
                    "Proposes a revision to the terms of the active embargo. "
                    "The wire form is the same as a first proposal; the "
                    "receiver's EM state makes it a revision."
                ),
                example="propose_embargo_revision",
                distinguisher=StateContext(
                    machine=EM,
                    states=(
                        EM.ACTIVE,
                        EM.REVISE,
                    ),
                ),
                howto=HowToGuide.MANAGE_EMBARGO,
                shorthand=ProtocolShorthand.EV,
            ),
            Occasion(
                when=(
                    "the CASE_MANAGER asks a Participant to answer embargo "
                    "terms another Participant proposed"
                ),
                anchor="relay-embargo-proposal",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Ask a participant about proposed embargo terms",
                description=(
                    "Asks one participant to accept or reject proposed "
                    "embargo terms, or a proposed revision. The CASE_MANAGER "
                    "sends one to each participant other than the proposer, "
                    "naming the proposer in `attributedTo`, and the "
                    "participant's answer names this Invite."
                ),
                example="relay_embargo_proposal",
                howto=HowToGuide.ESTABLISH_EMBARGO,
                notes=(
                    "The wire form is the Embargo Proposal (EP) or Embargo "
                    "Revision Proposal (EV) a participant sends; only its "
                    "sender and addressee differ."
                ),
            ),
        ),
        page=MessagePage.EM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        pattern=AcceptInviteToEmbargoOnCasePattern,
        event_class=AcceptInviteToEmbargoOnCaseReceivedEvent,
        use_case_class=AcceptInviteToEmbargoOnCaseReceivedUseCase,
        phrase="{actor} accepted the embargo",
        wire_activity_class=_EmAcceptEmbargoActivity,
        include_activity=True,
        # A Participant's answer is its own consent and carries no shorthand
        # (MSM-02-010, MSM-07-001): EA and EC are the Case Owner's decision.
        occasions=(
            Occasion(
                when="a Participant agrees to proposed embargo terms",
                anchor="agree-to-embargo-proposal",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Agree to proposed embargo terms",
                description=(
                    "Records the sender's own consent to the proposed terms. "
                    "The embargo becomes active only when the Case Owner sends"
                    " its decision."
                ),
                example="accept_embargo",
                distinguisher=StateContext(machine=EM, states=(EM.PROPOSED,)),
                howto=HowToGuide.ESTABLISH_EMBARGO,
            ),
            Occasion(
                when="a Participant agrees to a proposed embargo revision",
                anchor="agree-to-embargo-revision",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Agree to an embargo revision",
                description=(
                    "Records the sender's own consent to the revision. The "
                    "revision replaces the active embargo only when the Case "
                    "Owner sends its decision."
                ),
                example="accept_embargo_revision",
                distinguisher=StateContext(machine=EM, states=(EM.REVISE,)),
                howto=HowToGuide.MANAGE_EMBARGO,
            ),
        ),
        page=MessagePage.EM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        pattern=RejectInviteToEmbargoOnCasePattern,
        event_class=RejectInviteToEmbargoOnCaseReceivedEvent,
        use_case_class=RejectInviteToEmbargoOnCaseReceivedUseCase,
        phrase="{actor} declined the embargo",
        wire_activity_class=_EmRejectEmbargoActivity,
        include_activity=True,
        # A Participant's Reject is its own consent and carries no shorthand
        # (MSM-02-010, MSM-07-004); the CASE_MANAGER's Reject abandons the
        # proposal and is ER (MSM-02-006, MSM-07-016, EMB-16-001).
        occasions=(
            Occasion(
                when="a Participant refuses proposed embargo terms",
                anchor="refuse-embargo-proposal",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Refuse proposed embargo terms",
                description=(
                    "Records the sender's own refusal of the proposed terms. "
                    "The proposal is rejected for the case only when the Case "
                    "Owner sends its decision."
                ),
                example="reject_embargo",
                distinguisher=StateContext(machine=EM, states=(EM.PROPOSED,)),
                howto=HowToGuide.ESTABLISH_EMBARGO,
            ),
            Occasion(
                when="a Participant refuses a proposed embargo revision",
                anchor="refuse-embargo-revision",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Refuse an embargo revision",
                description=(
                    "Records the sender's own refusal of the revision. The "
                    "Case Owner keeps the prior terms by sending its decision."
                ),
                example="reject_embargo_revision",
                distinguisher=StateContext(machine=EM, states=(EM.REVISE,)),
                howto=HowToGuide.MANAGE_EMBARGO,
            ),
            Occasion(
                when=(
                    "the CASE_MANAGER abandons an open embargo proposal it "
                    "received once the case is public, an exploit is public "
                    "or attacks are observed"
                ),
                anchor="abandon-embargo-proposal",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Abandon embargo proposal",
                description=(
                    "Cancels the proposal for the case. The CASE_MANAGER then "
                    "withdraws each Invite it relayed for the proposal. This "
                    "Reject is not the CASE_MANAGER's consent."
                ),
                example="abandon_embargo_proposal",
                shorthand=ProtocolShorthand.ER,
                notes=(
                    "Each participant learns of it from the case ledger, "
                    "so it is addressed to nobody."
                ),
            ),
        ),
        page=MessagePage.EM,
    ),
    # The CASE_MANAGER's withdrawal of an Invite it sent (ADR-0152): an actor
    # undoes only an activity it performed.  Only the CASE_MANAGER sends it,
    # and a participant learns it from the ledger, so no received use case
    # handles it (ADR-0140 item 5).
    SemanticEntry(
        semantics=MessageSemantics.UNDO_INVITE_TO_EMBARGO_ON_CASE,
        pattern=UndoInviteToEmbargoOnCasePattern,
        event_class=UndoInviteToEmbargoOnCaseReceivedEvent,
        use_case_class=None,
        phrase="{actor} withdrew the embargo invitation",
        wire_activity_class=_EmUndoEmbargoInviteActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the CASE_MANAGER abandons an open embargo proposal "
                    "once the case is public, an exploit is public or "
                    "attacks are observed"
                ),
                anchor="withdraw-embargo-invite",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Withdraw an embargo invitation",
                description=(
                    "Withdraws an Invite the CASE_MANAGER sent for the "
                    "abandoned proposal. The CASE_MANAGER first rejects the "
                    "proposal it received, which cancels it, then withdraws "
                    "each Invite it relayed for it. When the CASE_MANAGER "
                    "made the proposal itself, withdrawing that proposal is "
                    "the cancel."
                ),
                example="undo_embargo_invite",
                notes=(
                    "Each participant learns of it from the case ledger, "
                    "so it is addressed to nobody."
                ),
            ),
        ),
        page=MessagePage.EM,
    ),
]
