"""Registry entries attaching an embargo event to, or removing it from, a case."""

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
    AnnounceEmbargoEventToCaseReceivedEvent,
    RemoveEmbargoEventFromCaseReceivedEvent,
)
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.use_cases.received.embargo import (
    AnnounceEmbargoEventToCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
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
    AnnounceEmbargoEventToCasePattern,
    RemoveEmbargoEventFromCasePattern,
)
from vultron.wire.as2.vocab.activities.embargo import (
    _AnnounceEmbargoActivity,
    _RemoveEmbargoFromCaseActivity,
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
                    "the CASE_MANAGER ends the active embargo, on its own "
                    "decision or on the Case Owner's"
                ),
                anchor="embargo-termination-notice",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Tell a participant the embargo has ended",
                description=(
                    "Tells one participant that the embargo has ended, with "
                    "immediate effect. The CASE_MANAGER sends one to each "
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
                    "the CASE_MANAGER states the terms of the embargo in force"
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
                    "the CASE_MANAGER has applied an Embargo Termination a "
                    "Case Owner sent before the end time"
                ),
                anchor="announce-embargo-termination",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Announce embargo termination",
                description=(
                    "Tells the active participants other than the "
                    "CASE_MANAGER and any Closed Participant that the embargo "
                    "it names is terminated. It proposes nothing."
                ),
                example="announce_embargo_termination",
                distinguisher=StateContext(
                    machine=EmbargoRegisterStatus,
                    states=(EmbargoRegisterStatus.TERMINATED,),
                ),
                howto=HowToGuide.MANAGE_EMBARGO,
                notes=(
                    "A termination the CASE_MANAGER starts itself, or one at "
                    "the end time, sends no announcement: after the end time, "
                    "the CASE_MANAGER's own end-time check ends the embargo "
                    "before it applies a Case Owner's termination."
                ),
            ),
        ),
        page=MessagePage.EM,
    ),
]
