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
    CreateCaseParticipantReceivedEvent,
    RemoveCaseParticipantFromCaseReceivedEvent,
    UpdateCaseParticipantReceivedEvent,
)
from vultron.core.use_cases.received.case_participant import (
    AddCaseParticipantToCaseReceivedUseCase,
    RemoveCaseParticipantFromCaseReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    HowToGuide,
    MessagePage,
    Occasion,
)
from vultron.wire.as2.extractor import (
    AddCaseParticipantToCasePattern,
    CreateCaseParticipantPattern,
    RemoveCaseParticipantFromCasePattern,
    UpdateCaseParticipantPattern,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    _AddParticipantToCaseActivity,
    _CreateParticipantActivity,
    _RemoveParticipantFromCaseActivity,
    _UpdateParticipantActivity,
)

ENTRIES: list[SemanticEntry] = [
    SemanticEntry(
        semantics=MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE,
        pattern=AddCaseParticipantToCasePattern,
        event_class=AddCaseParticipantToCaseReceivedEvent,
        use_case_class=AddCaseParticipantToCaseReceivedUseCase,
        phrase="{actor} added {object} as a case participant",
        wire_activity_class=_AddParticipantToCaseActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when="the Case Owner reinstates a removed Participant",
                anchor="add-case-participant-to-case",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Add case participant to case",
                description=(
                    "Asks the Case Manager to reinstate the participant record"
                    " named by the object. The Participant becomes active "
                    "again and receives the ledger entries it missed."
                ),
                example="add_coordinator_participant_to_case",
                howto=HowToGuide.MANAGE_PARTICIPANTS,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE,
        pattern=RemoveCaseParticipantFromCasePattern,
        event_class=RemoveCaseParticipantFromCaseReceivedEvent,
        use_case_class=RemoveCaseParticipantFromCaseReceivedUseCase,
        phrase="{actor} removed {object} from the case",
        wire_activity_class=_RemoveParticipantFromCaseActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Owner removes a Participant from active "
                    "participation"
                ),
                anchor="remove-case-participant-from-case",
                addressee=AddresseeSide.CASE_MANAGER,
                heading="Remove case participant from case",
                description=(
                    "Asks the Case Manager to remove the participant record "
                    "named by the object. The removed Participant receives a "
                    "direct notice."
                ),
                example="remove_participant_from_case",
                howto=HowToGuide.MANAGE_PARTICIPANTS,
            ),
        ),
        page=MessagePage.CASE_MANAGEMENT,
    ),
    # The CASE_MANAGER's own acts on participant records, each committed as
    # its own entry carrying the record in full (ADR-0114, CLP-07-013).  Only
    # the CASE_MANAGER sends them, and a participant takes the record from
    # the ledger, so no received use case handles them (ADR-0140 item 5).
    SemanticEntry(
        semantics=MessageSemantics.CREATE_CASE_PARTICIPANT,
        pattern=CreateCaseParticipantPattern,
        event_class=CreateCaseParticipantReceivedEvent,
        use_case_class=None,
        phrase="{actor} created a participant record",
        wire_activity_class=_CreateParticipantActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "the Case Manager creates a participant record, such as "
                    "the inert record for the invitee of a stub Invite"
                ),
                anchor="create-case-participant",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Create case participant",
                description=(
                    "Carries the new participant record in full: its roles, "
                    "statuses, joined mark and consent rows."
                ),
                example="create_participant",
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
                    "the Case Manager changes a participant record, such as "
                    "moving the CASE_OWNER role on an ownership transfer"
                ),
                anchor="update-case-participant",
                addressee=AddresseeSide.PARTICIPANT,
                heading="Update case participant",
                description=(
                    "Carries the changed participant record in full, as the "
                    "Case Manager stored it."
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
