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

from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.case_participant import (
    AddCaseParticipantToCaseReceivedEvent,
    CreateCaseParticipantReceivedEvent,
    RemoveCaseParticipantFromCaseReceivedEvent,
)
from vultron.core.use_cases.received.case_participant import (
    AddCaseParticipantToCaseReceivedUseCase,
    CreateCaseParticipantReceivedUseCase,
    RemoveCaseParticipantFromCaseReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.extractor import (
    AddCaseParticipantToCasePattern,
    CreateCaseParticipantPattern,
    RemoveCaseParticipantFromCasePattern,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    _AddParticipantToCaseActivity,
    _CreateParticipantActivity,
    _RemoveParticipantFromCaseActivity,
)

ENTRIES: list[SemanticEntry] = [
    SemanticEntry(
        semantics=MessageSemantics.CREATE_CASE_PARTICIPANT,
        pattern=CreateCaseParticipantPattern,
        event_class=CreateCaseParticipantReceivedEvent,
        use_case_class=CreateCaseParticipantReceivedUseCase,
        wire_activity_class=_CreateParticipantActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE,
        pattern=AddCaseParticipantToCasePattern,
        event_class=AddCaseParticipantToCaseReceivedEvent,
        use_case_class=AddCaseParticipantToCaseReceivedUseCase,
        wire_activity_class=_AddParticipantToCaseActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE,
        pattern=RemoveCaseParticipantFromCasePattern,
        event_class=RemoveCaseParticipantFromCaseReceivedEvent,
        use_case_class=RemoveCaseParticipantFromCaseReceivedUseCase,
        wire_activity_class=_RemoveParticipantFromCaseActivity,
    ),
]
