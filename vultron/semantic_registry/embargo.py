"""Embargo-domain semantic registry entries."""

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

from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
    ActivateEmbargoOnCaseReceivedEvent,
    AnnounceEmbargoEventToCaseReceivedEvent,
    InviteToEmbargoOnCaseReceivedEvent,
    RejectEmbargoProposalOnCaseReceivedEvent,
    RejectInviteToEmbargoOnCaseReceivedEvent,
    RemoveEmbargoEventFromCaseReceivedEvent,
    WithdrawFromEmbargoOnCaseReceivedEvent,
)
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    ActivateEmbargoOnCaseReceivedUseCase,
    AnnounceEmbargoEventToCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    RejectEmbargoProposalOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
    WithdrawFromEmbargoOnCaseReceivedUseCase,
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
    ActivateEmbargoOnCasePattern,
    AnnounceEmbargoEventToCasePattern,
    InviteToEmbargoOnCasePattern,
    RejectEmbargoProposalOnCasePattern,
    RejectInviteToEmbargoOnCasePattern,
    RemoveEmbargoEventFromCasePattern,
    WithdrawFromEmbargoOnCasePattern,
)
from vultron.wire.as2.vocab.activities.embargo import (
    _ActivateEmbargoActivity,
    _AnnounceEmbargoActivity,
    _EmAcceptEmbargoActivity,
    _EmProposeEmbargoActivity,
    _EmRejectEmbargoActivity,
    _RejectEmbargoProposalActivity,
    _RemoveEmbargoFromCaseActivity,
    _WithdrawFromEmbargoActivity,
)

ENTRIES: list[SemanticEntry] = [
    SemanticEntry(
        semantics=MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
        pattern=RemoveEmbargoEventFromCasePattern,
        event_class=RemoveEmbargoEventFromCaseReceivedEvent,
        use_case_class=RemoveEmbargoEventFromCaseReceivedUseCase,
        phrase="{actor} removed an embargo from the case",
        wire_activity_class=_RemoveEmbargoFromCaseActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="the Case Owner terminates the active embargo",
                anchor="embargo-termination",
                description="Terminates the embargo with immediate effect.",
                example="remove_embargo",
                howto=HowToGuide.MANAGE_EMBARGO,
                shorthand=ProtocolShorthand.ET,
            ),
        ),
        page=MessagePage.EM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE,
        pattern=AnnounceEmbargoEventToCasePattern,
        event_class=AnnounceEmbargoEventToCaseReceivedEvent,
        use_case_class=AnnounceEmbargoEventToCaseReceivedUseCase,
        phrase="{actor} announced an embargo change",
        wire_activity_class=_AnnounceEmbargoActivity,
        # The use case's door check reads to/cc (HP-01-005, ADR-0118).
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Manager states the terms of the embargo in force"
                ),
                anchor="announce-embargo",
                heading="Announce embargo",
                description=(
                    "Tells participants the terms of the active embargo. It "
                    "proposes nothing."
                ),
                example="announce_embargo",
                howto=HowToGuide.MANAGE_EMBARGO,
            ),
        ),
        page=MessagePage.EM,
    ),
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
        occasions=(
            Occasion(
                when="a Participant agrees to proposed embargo terms",
                anchor="embargo-proposal-acceptance",
                description=(
                    "Records the sender's own consent to the proposed terms. "
                    "The embargo becomes active only when the Case Owner sends"
                    " its decision."
                ),
                example="accept_embargo",
                distinguisher=StateContext(machine=EM, states=(EM.PROPOSED,)),
                howto=HowToGuide.ESTABLISH_EMBARGO,
                shorthand=ProtocolShorthand.EA,
            ),
            Occasion(
                when="a Participant agrees to a proposed embargo revision",
                anchor="embargo-revision-acceptance",
                description=(
                    "Records the sender's own consent to the revision. The "
                    "revision replaces the active embargo only when the Case "
                    "Owner sends its decision."
                ),
                example="accept_embargo_revision",
                distinguisher=StateContext(machine=EM, states=(EM.REVISE,)),
                howto=HowToGuide.MANAGE_EMBARGO,
                shorthand=ProtocolShorthand.EC,
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
        occasions=(
            Occasion(
                when="a Participant refuses proposed embargo terms",
                anchor="embargo-proposal-rejection",
                description=(
                    "Records the sender's own refusal of the proposed terms. "
                    "The proposal is rejected for the case only when the Case "
                    "Owner sends its decision."
                ),
                example="reject_embargo",
                distinguisher=StateContext(machine=EM, states=(EM.PROPOSED,)),
                howto=HowToGuide.ESTABLISH_EMBARGO,
                shorthand=ProtocolShorthand.ER,
            ),
            Occasion(
                when="a Participant refuses a proposed embargo revision",
                anchor="embargo-revision-rejection",
                description=(
                    "Records the sender's own refusal of the revision. The "
                    "Case Owner keeps the prior terms by sending its decision."
                ),
                example="reject_embargo_revision",
                distinguisher=StateContext(machine=EM, states=(EM.REVISE,)),
                howto=HowToGuide.MANAGE_EMBARGO,
                shorthand=ProtocolShorthand.EJ,
            ),
        ),
        page=MessagePage.EM,
    ),
    # The case owner's decision for the case (ADR-0122): Accept/Reject of
    # the EmbargoEvent itself, never of the Invite that proposed it.
    SemanticEntry(
        semantics=MessageSemantics.ACTIVATE_EMBARGO_ON_CASE,
        pattern=ActivateEmbargoOnCasePattern,
        event_class=ActivateEmbargoOnCaseReceivedEvent,
        use_case_class=ActivateEmbargoOnCaseReceivedUseCase,
        phrase="{actor} activated the embargo",
        wire_activity_class=_ActivateEmbargoActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="the Case Owner decides to activate a proposed embargo",
                anchor="activate-embargo",
                heading="Activate embargo",
                description=(
                    "Activates the proposal for the case. If an embargo is "
                    "already active, the proposal replaces it."
                ),
                example="activate_embargo",
                howto=HowToGuide.MANAGE_EMBARGO,
            ),
        ),
        page=MessagePage.EM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE,
        pattern=RejectEmbargoProposalOnCasePattern,
        event_class=RejectEmbargoProposalOnCaseReceivedEvent,
        use_case_class=RejectEmbargoProposalOnCaseReceivedUseCase,
        phrase="{actor} rejected the proposed embargo",
        wire_activity_class=_RejectEmbargoProposalActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="the Case Owner decides to reject a proposed embargo",
                anchor="reject-embargo-proposal",
                heading="Reject embargo proposal",
                description=(
                    "Rejects the proposal for the case. An active embargo "
                    "stays in force on its current terms."
                ),
                example="reject_embargo_proposal",
                howto=HowToGuide.MANAGE_EMBARGO,
            ),
        ),
        page=MessagePage.EM,
    ),
    # A signatory's withdrawal from the embargo in force (MSM-07-010,
    # ADR-0122): Leave of the EmbargoEvent, never a Reject of an Invite.
    SemanticEntry(
        semantics=MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE,
        pattern=WithdrawFromEmbargoOnCasePattern,
        event_class=WithdrawFromEmbargoOnCaseReceivedEvent,
        use_case_class=WithdrawFromEmbargoOnCaseReceivedUseCase,
        phrase="{actor} withdrew from the embargo",
        wire_activity_class=_WithdrawFromEmbargoActivity,
        # The use case's door check reads to/cc (HP-01-005, ADR-0118).
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "a Participant bound by the active embargo stops "
                    "complying with it"
                ),
                anchor="embargo-withdrawal",
                heading="Withdraw from embargo",
                description=(
                    "Ends the sender's own consent to the embargo in force, "
                    "and to any revision it had agreed to. The embargo stays "
                    "in force for every other participant."
                ),
                example="withdraw_from_embargo",
                howto=HowToGuide.MANAGE_EMBARGO,
            ),
        ),
        page=MessagePage.EM,
    ),
]
