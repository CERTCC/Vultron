"""Case and full-case invitation registry entries, and case announcements."""

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
    AcceptInviteActorToCaseReceivedEvent,
    AcceptInviteActorToFullCaseReceivedEvent,
    AnnounceVulnerabilityCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    InviteActorToFullCaseReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
    RejectInviteActorToFullCaseReceivedEvent,
    TentativeRejectInviteActorToFullCaseReceivedEvent,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.use_cases.received.actor import (
    AcceptInviteActorToCaseReceivedUseCase,
    AcceptInviteActorToFullCaseReceivedUseCase,
    AnnounceVulnerabilityCaseReceivedUseCase,
    InviteActorToCaseReceivedUseCase,
    InviteActorToFullCaseReceivedUseCase,
    RejectInviteActorToCaseReceivedUseCase,
    RejectInviteActorToFullCaseReceivedUseCase,
    TentativeRejectInviteActorToFullCaseReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    HowToGuide,
    MessagePage,
    Occasion,
    ProtocolShorthand,
)
from vultron.wire.as2.extractor import (
    AcceptInviteActorToCasePattern,
    AcceptInviteActorToFullCasePattern,
    AnnounceVulnerabilityCasePattern,
    InviteActorToCasePattern,
    InviteActorToFullCasePattern,
    RejectInviteActorToCasePattern,
    RejectInviteActorToFullCasePattern,
    TentativeRejectInviteActorToFullCasePattern,
)
from vultron.wire.as2.vocab.activities.case.content import (
    _AnnounceVulnerabilityCaseActivity,
)
from vultron.wire.as2.vocab.activities.case.invite import (
    _RmAcceptFullCaseInviteActivity,
    _RmAcceptInviteToCaseActivity,
    _RmInviteToCaseActivity,
    _RmInviteToFullCaseActivity,
    _RmRejectFullCaseInviteActivity,
    _RmRejectInviteToCaseActivity,
    _RmTentativeRejectFullCaseInviteActivity,
)

ENTRIES: list[SemanticEntry] = [
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
                when="the CASE_MANAGER invites an actor to join the case",
                anchor="invite-actor-to-case",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Invite actor to case",
                description=(
                    "Sends a Stub Invite carrying the case stub and the "
                    "embargo terms the invitee would agree to."
                ),
                example="invite_to_case",
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
                    "the CASE_MANAGER has replayed the case ledger to a newly "
                    "joined Participant"
                ),
                anchor="invite-actor-to-full-case",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Send Full-Case Invite",
                description=(
                    "Sends the Full-Case Invite, which asks the Participant to"
                    " judge the case. It carries the CASE_MANAGER's ledger "
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
                    "the CASE_MANAGER has admitted a new Participant to the "
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
