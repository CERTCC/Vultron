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

from vultron.core.behaviors.sender_entitlement import AddresseeSide
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedEvent,
    ActivateEmbargoOnCaseReceivedEvent,
    AnnounceEmbargoEventToCaseReceivedEvent,
    CreateEmbargoConsentReceivedEvent,
    CreateEmbargoEventReceivedEvent,
    InviteToEmbargoOnCaseReceivedEvent,
    RejectEmbargoProposalOnCaseReceivedEvent,
    RejectInviteToEmbargoOnCaseReceivedEvent,
    RemoveEmbargoEventFromCaseReceivedEvent,
    UndoInviteToEmbargoOnCaseReceivedEvent,
    UpdateEmbargoConsentReceivedEvent,
    WithdrawFromEmbargoOnCaseReceivedEvent,
)
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import EmbargoRegisterStatus
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
    CreateEmbargoConsentPattern,
    CreateEmbargoEventPattern,
    InviteToEmbargoOnCasePattern,
    RejectEmbargoProposalOnCasePattern,
    RejectInviteToEmbargoOnCasePattern,
    RemoveEmbargoEventFromCasePattern,
    UndoInviteToEmbargoOnCasePattern,
    UpdateEmbargoConsentPattern,
    WithdrawFromEmbargoOnCasePattern,
)
from vultron.wire.as2.vocab.activities.embargo import (
    _ActivateEmbargoActivity,
    _AnnounceEmbargoActivity,
    _CreateEmbargoConsentActivity,
    _CreateEmbargoEventActivity,
    _EmAcceptEmbargoActivity,
    _EmProposeEmbargoActivity,
    _EmRejectEmbargoActivity,
    _EmUndoEmbargoInviteActivity,
    _RejectEmbargoProposalActivity,
    _RemoveEmbargoFromCaseActivity,
    _UpdateEmbargoConsentActivity,
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
                addressee=AddresseeSide.CASE_MANAGER,
                description="Terminates the embargo with immediate effect.",
                example="remove_embargo",
                howto=HowToGuide.MANAGE_EMBARGO,
                shorthand=ProtocolShorthand.ET,
            ),
            Occasion(
                when=(
                    "the Case Manager ends the active embargo, on its own "
                    "decision or on the Case Owner's"
                ),
                anchor="embargo-termination-notice",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Tell a participant the embargo has ended",
                description=(
                    "Tells one participant that the embargo has ended, with "
                    "immediate effect. The Case Manager sends one to each "
                    "participant other than itself, naming the Case Owner in "
                    "`attributedTo` when the Case Owner asked for the "
                    "termination."
                ),
                example="notify_embargo_termination",
                howto=HowToGuide.MANAGE_EMBARGO,
                notes=(
                    "The wire form is the Embargo Termination (ET) a Case "
                    "Owner sends; only its sender and addressee differ."
                ),
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
        # The use case's door check reads `to` (HP-01-005, ADR-0118).
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Manager states the terms of the embargo in force"
                ),
                anchor="announce-embargo",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Announce embargo",
                description=(
                    "Tells participants the terms of the active embargo. It "
                    "proposes nothing."
                ),
                example="announce_embargo",
                distinguisher=StateContext(
                    machine=EmbargoRegisterStatus,
                    states=(EmbargoRegisterStatus.ACTIVE,),
                ),
                howto=HowToGuide.MANAGE_EMBARGO,
            ),
            Occasion(
                when=(
                    "the Case Manager has applied an Embargo Termination a "
                    "Case Owner sent before the end time"
                ),
                anchor="announce-embargo-termination",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Announce embargo termination",
                description=(
                    "Tells the active participants other than the Case "
                    "Manager and any Closed Participant that the embargo it "
                    "names is terminated. It proposes nothing."
                ),
                example="announce_embargo_termination",
                distinguisher=StateContext(
                    machine=EmbargoRegisterStatus,
                    states=(EmbargoRegisterStatus.TERMINATED,),
                ),
                howto=HowToGuide.MANAGE_EMBARGO,
                notes=(
                    "A termination the Case Manager starts itself, or one at "
                    "the end time, sends no announcement: after the end time, "
                    "the Case Manager's own end-time check ends the embargo "
                    "before it applies a Case Owner's termination."
                ),
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
                    "the Case Manager asks a Participant to answer embargo "
                    "terms another Participant proposed"
                ),
                anchor="relay-embargo-proposal",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Ask a participant about proposed embargo terms",
                description=(
                    "Asks one participant to accept or reject proposed "
                    "embargo terms, or a proposed revision. The Case Manager "
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
        occasions=(
            Occasion(
                when="a Participant agrees to proposed embargo terms",
                anchor="embargo-proposal-acceptance",
                addressee=AddresseeSide.CASE_MANAGER,
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
                addressee=AddresseeSide.CASE_MANAGER,
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
                addressee=AddresseeSide.CASE_MANAGER,
                description=(
                    "Records the sender's own refusal of the proposed terms. "
                    "The proposal is rejected for the case only when the Case "
                    "Owner sends its decision."
                ),
                example="reject_embargo",
                distinguisher=StateContext(machine=EM, states=(EM.PROPOSED,)),
                howto=HowToGuide.ESTABLISH_EMBARGO,
                shorthand=ProtocolShorthand.ER,
                notes=(
                    "The Case Manager sends the same activity when it "
                    "abandons an open proposal once the case is public, an "
                    "exploit is public or attacks are observed. Its Reject "
                    "cancels the proposal, and each Invite it relayed for "
                    "the proposal is then withdrawn."
                ),
            ),
            Occasion(
                when="a Participant refuses a proposed embargo revision",
                anchor="embargo-revision-rejection",
                addressee=AddresseeSide.CASE_MANAGER,
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
                    "the Case Manager abandons an open embargo proposal "
                    "once the case is public, an exploit is public or "
                    "attacks are observed"
                ),
                anchor="withdraw-embargo-invite",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Withdraw an embargo invitation",
                description=(
                    "Withdraws an Invite the Case Manager sent for the "
                    "abandoned proposal. The Case Manager first rejects the "
                    "proposal it received, which cancels it, then withdraws "
                    "each Invite it relayed for it. When the Case Manager "
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
                addressee=AddresseeSide.CASE_MANAGER,
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
                addressee=AddresseeSide.CASE_MANAGER,
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
                addressee=AddresseeSide.CASE_MANAGER,
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
    # The CASE_MANAGER's own records: an embargo its case's creation wrote,
    # and its acts on consent rows, each committed as its own entry carrying
    # the record in full (ADR-0122, CLP-07-013).  Only the CASE_MANAGER commits
    # them, and a participant takes the record from the ledger, so no
    # received use case handles them (ADR-0140 item 5).
    SemanticEntry(
        semantics=MessageSemantics.CREATE_EMBARGO_EVENT,
        pattern=CreateEmbargoEventPattern,
        event_class=CreateEmbargoEventReceivedEvent,
        use_case_class=None,
        phrase="{actor} created the case's embargo",
        wire_activity_class=_CreateEmbargoEventActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Manager has created a case and, with it, an "
                    "embargo such as the default embargo"
                ),
                anchor="create-embargo-event",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Create embargo event",
                description=(
                    "Carries the new embargo in full, its start and end "
                    "times included. It follows the case's genesis entry."
                ),
                example="create_embargo_event",
                notes=(
                    "Each participant learns of it from the case ledger, so "
                    "it is addressed to nobody."
                ),
            ),
        ),
        page=MessagePage.EM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.CREATE_EMBARGO_CONSENT,
        pattern=CreateEmbargoConsentPattern,
        event_class=CreateEmbargoConsentReceivedEvent,
        use_case_class=None,
        phrase="{actor} created an embargo consent row",
        wire_activity_class=_CreateEmbargoConsentActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Manager creates a participant's consent row "
                    "for an embargo, such as the UNINVITED row a proposal "
                    "writes"
                ),
                anchor="create-embargo-consent",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Create embargo consent",
                description=(
                    "Carries the new consent row in full: the embargo it "
                    "answers, the participant it belongs to and its state."
                ),
                example="create_embargo_consent",
                notes=(
                    "Each participant learns of it from the case ledger, so "
                    "it is addressed to nobody."
                ),
            ),
        ),
        page=MessagePage.EM,
    ),
    SemanticEntry(
        semantics=MessageSemantics.UPDATE_EMBARGO_CONSENT,
        pattern=UpdateEmbargoConsentPattern,
        event_class=UpdateEmbargoConsentReceivedEvent,
        use_case_class=None,
        phrase="{actor} updated an embargo consent row",
        wire_activity_class=_UpdateEmbargoConsentActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Manager changes a participant's consent row, "
                    "such as an invitation timing out, the rows carried over "
                    "at activation or a change of its own consent"
                ),
                anchor="update-embargo-consent",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Update embargo consent",
                description=(
                    "Carries the changed consent row in full. A Case Manager "
                    "with an embargo stake of its own records a change of "
                    "its own consent this way, never as a Reject of the "
                    "Invite."
                ),
                example="update_embargo_consent",
                notes=(
                    "Each participant learns of it from the case ledger, so "
                    "it is addressed to nobody."
                ),
            ),
        ),
        page=MessagePage.EM,
    ),
]
