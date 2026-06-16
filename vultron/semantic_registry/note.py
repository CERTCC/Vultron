"""Note-domain semantic registry entries."""

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
from vultron.core.models.events.note import (
    AddNoteToCaseReceivedEvent,
    CreateNoteReceivedEvent,
    RemoveNoteFromCaseReceivedEvent,
)
from vultron.core.use_cases.received.note import (
    AddNoteToCaseReceivedUseCase,
    CreateNoteReceivedUseCase,
    RemoveNoteFromCaseReceivedUseCase,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.extractor import (
    AddNoteToCaseActivityPattern,
    CreateNotePattern,
    RemoveNoteFromCasePattern,
)
from vultron.wire.as2.vocab.activities.case import (
    _AddNoteToCaseActivity,
)

ENTRIES: list[SemanticEntry] = [
    SemanticEntry(
        semantics=MessageSemantics.CREATE_NOTE,
        pattern=CreateNotePattern,
        event_class=CreateNoteReceivedEvent,
        use_case_class=CreateNoteReceivedUseCase,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ADD_NOTE_TO_CASE,
        pattern=AddNoteToCaseActivityPattern,
        event_class=AddNoteToCaseReceivedEvent,
        use_case_class=AddNoteToCaseReceivedUseCase,
        wire_activity_class=_AddNoteToCaseActivity,
        include_activity=True,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REMOVE_NOTE_FROM_CASE,
        pattern=RemoveNoteFromCasePattern,
        event_class=RemoveNoteFromCaseReceivedEvent,
        use_case_class=RemoveNoteFromCaseReceivedUseCase,
    ),
]
