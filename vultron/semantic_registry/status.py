"""Status-domain semantic registry entries.

Covers both case-level and participant-level status entries.
"""

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
from vultron.core.models.events.status import (
    AddCaseStatusToCaseReceivedEvent,
    AddParticipantStatusToParticipantReceivedEvent,
    CreateCaseStatusReceivedEvent,
    CreateParticipantStatusReceivedEvent,
)
from vultron.core.use_cases.received.status import (
    AddCaseStatusToCaseReceivedUseCase,
    AddParticipantStatusToParticipantReceivedUseCase,
    CreateCaseStatusReceivedUseCase,
    CreateParticipantStatusReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.extractor import (
    AddCaseStatusToCasePattern,
    AddParticipantStatusToParticipantPattern,
    CreateCaseStatusActivityPattern,
    CreateParticipantStatusPattern,
)
from vultron.wire.as2.vocab.activities.case import (
    _AddStatusToCaseActivity,
    _CreateCaseStatusActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    _AddStatusToParticipantActivity,
    _CreateStatusForParticipantActivity,
)

ENTRIES: list[SemanticEntry] = [
    # Case status
    SemanticEntry(
        semantics=MessageSemantics.CREATE_CASE_STATUS,
        pattern=CreateCaseStatusActivityPattern,
        event_class=CreateCaseStatusReceivedEvent,
        use_case_class=CreateCaseStatusReceivedUseCase,
        wire_activity_class=_CreateCaseStatusActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ADD_CASE_STATUS_TO_CASE,
        pattern=AddCaseStatusToCasePattern,
        event_class=AddCaseStatusToCaseReceivedEvent,
        use_case_class=AddCaseStatusToCaseReceivedUseCase,
        wire_activity_class=_AddStatusToCaseActivity,
    ),
    # Participant status
    SemanticEntry(
        semantics=MessageSemantics.CREATE_PARTICIPANT_STATUS,
        pattern=CreateParticipantStatusPattern,
        event_class=CreateParticipantStatusReceivedEvent,
        use_case_class=CreateParticipantStatusReceivedUseCase,
        wire_activity_class=_CreateStatusForParticipantActivity,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
        pattern=AddParticipantStatusToParticipantPattern,
        event_class=AddParticipantStatusToParticipantReceivedEvent,
        use_case_class=AddParticipantStatusToParticipantReceivedUseCase,
        wire_activity_class=_AddStatusToParticipantActivity,
    ),
]
