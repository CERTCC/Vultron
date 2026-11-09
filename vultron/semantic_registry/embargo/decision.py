"""Registry entries for the Case Owner's embargo decision and withdrawal from it."""

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
    ActivateEmbargoOnCaseReceivedEvent,
    RejectEmbargoProposalOnCaseReceivedEvent,
    WithdrawFromEmbargoOnCaseReceivedEvent,
)
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    ActivateEmbargoOnCaseReceivedUseCase,
    RejectEmbargoProposalOnCaseReceivedUseCase,
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
    ActivateEmbargoOnCasePattern,
    RejectEmbargoProposalOnCasePattern,
    WithdrawFromEmbargoOnCasePattern,
)
from vultron.wire.as2.vocab.activities.embargo import (
    _ActivateEmbargoActivity,
    _RejectEmbargoProposalActivity,
    _WithdrawFromEmbargoActivity,
)

ENTRIES: list[SemanticEntry] = [
    # The Case Owner's decision for the case (ADR-0122, ADR-0180): Add/Reject
    # of the EmbargoEvent itself, never of the Invite that proposed it.  It
    # carries EA, EC, ER and EJ, told apart by the case's EM state (MSM-02).
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
                when=(
                    "the Case Owner decides to activate a proposed embargo "
                    "for a case with no active embargo"
                ),
                anchor="embargo-proposal-acceptance",
                addressee=AddresseeSide.CASE_MANAGER,
                description=(
                    "Activates the proposal for the case. Any other open "
                    "proposal stays open as a revision."
                ),
                example="activate_embargo",
                distinguisher=StateContext(machine=EM, states=(EM.PROPOSED,)),
                howto=HowToGuide.ESTABLISH_EMBARGO,
                shorthand=ProtocolShorthand.EA,
            ),
            Occasion(
                when=(
                    "the Case Owner decides to replace the active embargo "
                    "with a proposed revision"
                ),
                anchor="embargo-revision-acceptance",
                addressee=AddresseeSide.CASE_MANAGER,
                description=(
                    "Activates the revision for the case. It replaces the "
                    "active embargo in the same register step."
                ),
                example="activate_embargo_revision",
                distinguisher=StateContext(machine=EM, states=(EM.REVISE,)),
                howto=HowToGuide.MANAGE_EMBARGO,
                shorthand=ProtocolShorthand.EC,
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
            # ER is also the CASE_MANAGER's abandoning Reject of the Invite,
            # an expansion, so this section needs a heading (MSM-08-008).
            Occasion(
                when=(
                    "the Case Owner decides to reject a proposed embargo "
                    "for a case with no active embargo"
                ),
                anchor="reject-embargo-proposal",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Reject embargo proposal",
                description=(
                    "Rejects the proposal for the case. The case has no "
                    "embargo once no other proposal is open."
                ),
                example="reject_embargo_proposal",
                distinguisher=StateContext(machine=EM, states=(EM.PROPOSED,)),
                howto=HowToGuide.ESTABLISH_EMBARGO,
                shorthand=ProtocolShorthand.ER,
            ),
            Occasion(
                when="the Case Owner decides to reject a proposed revision",
                anchor="embargo-revision-rejection",
                addressee=AddresseeSide.CASE_MANAGER,
                description=(
                    "Rejects the revision for the case. The active embargo "
                    "stays in force on its prior terms, unless the case is "
                    "public, an exploit is public or attacks are observed, "
                    "when the CASE_MANAGER also ends it."
                ),
                example="reject_embargo_revision_proposal",
                distinguisher=StateContext(machine=EM, states=(EM.REVISE,)),
                howto=HowToGuide.MANAGE_EMBARGO,
                shorthand=ProtocolShorthand.EJ,
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
]
