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
    CreateEmbargoEventReceivedEvent,
    InviteToEmbargoOnCaseReceivedEvent,
    RejectEmbargoProposalOnCaseReceivedEvent,
    RejectInviteToEmbargoOnCaseReceivedEvent,
    RemoveEmbargoEventFromCaseReceivedEvent,
)
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    ActivateEmbargoOnCaseReceivedUseCase,
    AnnounceEmbargoEventToCaseReceivedUseCase,
    CreateEmbargoEventReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    RejectEmbargoProposalOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.extractor import (
    AcceptInviteToEmbargoOnCasePattern,
    ActivateEmbargoOnCasePattern,
    AnnounceEmbargoEventToCasePattern,
    CreateEmbargoEventPattern,
    InviteToEmbargoOnCasePattern,
    RejectEmbargoProposalOnCasePattern,
    RejectInviteToEmbargoOnCasePattern,
    RemoveEmbargoEventFromCasePattern,
)
from vultron.wire.as2.vocab.activities.embargo import (
    _ActivateEmbargoActivity,
    _AnnounceEmbargoActivity,
    _EmAcceptEmbargoActivity,
    _EmProposeEmbargoActivity,
    _EmRejectEmbargoActivity,
    _RejectEmbargoProposalActivity,
    _RemoveEmbargoFromCaseActivity,
)

ENTRIES: list[SemanticEntry] = [
    SemanticEntry(
        semantics=MessageSemantics.CREATE_EMBARGO_EVENT,
        pattern=CreateEmbargoEventPattern,
        event_class=CreateEmbargoEventReceivedEvent,
        use_case_class=CreateEmbargoEventReceivedUseCase,
        phrase="{actor} created an embargo event",
        # The use case's door check reads to/cc (HP-01-005, ADR-0118).
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
        pattern=RemoveEmbargoEventFromCasePattern,
        event_class=RemoveEmbargoEventFromCaseReceivedEvent,
        use_case_class=RemoveEmbargoEventFromCaseReceivedUseCase,
        phrase="{actor} removed an embargo from the case",
        wire_activity_class=_RemoveEmbargoFromCaseActivity,
        include_activity=True,
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
    ),
    SemanticEntry(
        semantics=MessageSemantics.INVITE_TO_EMBARGO_ON_CASE,
        pattern=InviteToEmbargoOnCasePattern,
        event_class=InviteToEmbargoOnCaseReceivedEvent,
        use_case_class=InviteToEmbargoOnCaseReceivedUseCase,
        phrase="{actor} proposed an embargo",
        wire_activity_class=_EmProposeEmbargoActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        pattern=AcceptInviteToEmbargoOnCasePattern,
        event_class=AcceptInviteToEmbargoOnCaseReceivedEvent,
        use_case_class=AcceptInviteToEmbargoOnCaseReceivedUseCase,
        phrase="{actor} accepted the embargo",
        wire_activity_class=_EmAcceptEmbargoActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        pattern=RejectInviteToEmbargoOnCasePattern,
        event_class=RejectInviteToEmbargoOnCaseReceivedEvent,
        use_case_class=RejectInviteToEmbargoOnCaseReceivedUseCase,
        phrase="{actor} declined the embargo",
        wire_activity_class=_EmRejectEmbargoActivity,
        include_activity=True,
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
    ),
    SemanticEntry(
        semantics=MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE,
        pattern=RejectEmbargoProposalOnCasePattern,
        event_class=RejectEmbargoProposalOnCaseReceivedEvent,
        use_case_class=RejectEmbargoProposalOnCaseReceivedUseCase,
        phrase="{actor} rejected the proposed embargo",
        wire_activity_class=_RejectEmbargoProposalActivity,
        include_activity=True,
    ),
]
