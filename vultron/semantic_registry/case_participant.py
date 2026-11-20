"""Case-participant management semantic registry entries."""

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
from vultron.core.models.events.case_participant import (
    AddCaseParticipantToCaseReceivedEvent,
    AnnounceAdmittedActReceivedEvent,
    ReinstateParticipantInCaseReceivedEvent,
    RemoveParticipantFromCaseReceivedEvent,
    UpdateCaseParticipantReceivedEvent,
)
from vultron.core.use_cases.received.case_participant import (
    AnnounceAdmittedActReceivedUseCase,
    ReinstateParticipantInCaseReceivedUseCase,
    RemoveParticipantFromCaseReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    HowToGuide,
    MessagePage,
    Occasion,
)
from vultron.wire.as2.extractor import (
    AddCaseParticipantToCasePattern,
    AnnounceAdmittedActPattern,
    ReinstateParticipantInCasePattern,
    RemoveParticipantFromCasePattern,
    UpdateCaseParticipantPattern,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    _AddParticipantToCaseActivity,
    _AnnounceAdmittedActActivity,
    _ReinstateParticipantActivity,
    _RemoveParticipantActivity,
    _UpdateParticipantActivity,
)

ENTRIES: list[SemanticEntry] = [
    # The Case Owner's own acts, naming the actor (ADR-0199): sent to the
    # CASE_MANAGER only, which admits each as its ledger entry or refuses it.
    SemanticEntry(
        semantics=MessageSemantics.REMOVE_PARTICIPANT_FROM_CASE,
        pattern=RemoveParticipantFromCasePattern,
        event_class=RemoveParticipantFromCaseReceivedEvent,
        use_case_class=RemoveParticipantFromCaseReceivedUseCase,
        phrase="{actor} removed {object} from the case",
        wire_activity_class=_RemoveParticipantActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Owner removes a Participant from active "
                    "participation"
                ),
                anchor="remove-participant-from-case",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Remove participant from case",
                description=(
                    "The Case Owner's own removal of the actor named by the "
                    "object, from the case named by the origin. The "
                    "CASE_MANAGER records it as the ledger entry and "
                    "announces it to the removed actor."
                ),
                example="remove_participant_from_case",
                howto=HowToGuide.MANAGE_PARTICIPANTS,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REINSTATE_PARTICIPANT_IN_CASE,
        pattern=ReinstateParticipantInCasePattern,
        event_class=ReinstateParticipantInCaseReceivedEvent,
        use_case_class=ReinstateParticipantInCaseReceivedUseCase,
        phrase="{actor} reinstated {object} in the case",
        wire_activity_class=_ReinstateParticipantActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="the Case Owner reinstates a removed Participant",
                anchor="reinstate-participant-in-case",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Reinstate participant in case",
                description=(
                    "The Case Owner's own reinstatement of the removed actor "
                    "named by the object. The CASE_MANAGER records it as the "
                    "ledger entry and announces it to the actor, which "
                    "becomes active again and receives the ledger entries it "
                    "missed."
                ),
                example="reinstate_participant_in_case",
                howto=HowToGuide.MANAGE_PARTICIPANTS,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    # The CASE_MANAGER's Announce of an act it admitted (ADR-0199): the most
    # general Announce of an activity, so it follows every Announce entry
    # that nests a specific act (SE-03-002).
    SemanticEntry(
        semantics=MessageSemantics.ANNOUNCE_ADMITTED_ACT,
        pattern=AnnounceAdmittedActPattern,
        event_class=AnnounceAdmittedActReceivedEvent,
        use_case_class=AnnounceAdmittedActReceivedUseCase,
        phrase="{actor} announced an act it admitted",
        wire_activity_class=_AnnounceAdmittedActActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the CASE_MANAGER has admitted an act that concerns an "
                    "actor the ledger fan-out does not reach, such as a "
                    "removed or reinstated Participant"
                ),
                anchor="announce-admitted-act",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Announce admitted act",
                description=(
                    "Carries the admitted act inline, as it was received, and "
                    "names it in inReplyTo. It informs and asks nothing: the "
                    "receiver takes the change from the ledger entry that "
                    "carries the act, never from the Announce."
                ),
                example="announce_participant_removal",
                howto=HowToGuide.MANAGE_PARTICIPANTS,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    # The CASE_MANAGER's own acts on participant records, each committed as
    # its own entry carrying the record in full (ADR-0114, CLP-07-021).  Only
    # the CASE_MANAGER sends them, and a participant takes the record from
    # the ledger, so no received use case handles them (ADR-0140 item 5).
    SemanticEntry(
        semantics=MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE,
        pattern=AddCaseParticipantToCasePattern,
        event_class=AddCaseParticipantToCaseReceivedEvent,
        use_case_class=None,
        phrase="{actor} added a participant record to the case",
        wire_activity_class=_AddParticipantToCaseActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the CASE_MANAGER adds a new participant record to the "
                    "case, such as the inert record for the invitee of a "
                    "stub Invite"
                ),
                anchor="add-case-participant-to-case",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Add case participant to case",
                description=(
                    "Carries the new participant record in full: its roles, "
                    "statuses, joined mark and consent rows. The target is "
                    "the case whose participant list the record joins."
                ),
                example="add_participant_to_case",
                notes=(
                    "Each participant learns of it from the case ledger, so "
                    "it is addressed to nobody."
                ),
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.UPDATE_CASE_PARTICIPANT,
        pattern=UpdateCaseParticipantPattern,
        event_class=UpdateCaseParticipantReceivedEvent,
        use_case_class=None,
        phrase="{actor} updated a participant record",
        wire_activity_class=_UpdateParticipantActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the CASE_MANAGER changes a participant record, such as "
                    "moving the CASE_OWNER role on an ownership transfer"
                ),
                anchor="update-case-participant",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Update case participant",
                description=(
                    "Carries the changed participant record in full, as the "
                    "CASE_MANAGER stored it."
                ),
                example="update_participant",
                notes=(
                    "Each participant learns of it from the case ledger, so "
                    "it is addressed to nobody."
                ),
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
]
