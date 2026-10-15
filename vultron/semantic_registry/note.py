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
from vultron.semantic_registry._occasion import (
    HowToGuide,
    MessagePage,
    Occasion,
    ProtocolShorthand,
)
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
        phrase="{actor} created a note",
        include_activity=True,
        occasions=(
            Occasion(
                when="a Participant posts a new note to the case",
                anchor="create-note",
                heading="Create note",
                description=(
                    "Creates a note and, when the note's context names the "
                    "case, posts it to that case: the Case Manager attaches "
                    "the note and records the attachment in the case "
                    "ledger. The Create carries no target. A receiver also "
                    "accepts a Create followed by an Add of the same note, "
                    "and the Add then changes nothing more. This "
                    "implementation's add-note trigger sends the Create "
                    "alone."
                ),
                example="create_note",
                howto=HowToGuide.STATUS_UPDATES,
                shorthand=ProtocolShorthand.GI,
            ),
        ),
        page=MessagePage.GENERAL,
    ),
    SemanticEntry(
        semantics=MessageSemantics.ADD_NOTE_TO_CASE,
        pattern=AddNoteToCaseActivityPattern,
        event_class=AddNoteToCaseReceivedEvent,
        use_case_class=AddNoteToCaseReceivedUseCase,
        phrase="{actor} added a note to the case",
        wire_activity_class=_AddNoteToCaseActivity,
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "a Participant attaches a note that already exists to "
                    "the case"
                ),
                anchor="add-note-to-case",
                heading="Add note to case",
                description=(
                    "Attaches the note to the case named by the target, and "
                    "the Case Manager records the attachment in the case "
                    "ledger. A receiver accepts it on its own, for a note "
                    "created earlier or elsewhere, or after a Create of the "
                    "same note. This implementation's add-note trigger does "
                    "not send it: a new note goes as a Create alone."
                ),
                example="add_note_to_case",
                howto=HowToGuide.STATUS_UPDATES,
                shorthand=ProtocolShorthand.GI,
            ),
        ),
        page=MessagePage.GENERAL,
    ),
    SemanticEntry(
        semantics=MessageSemantics.REMOVE_NOTE_FROM_CASE,
        pattern=RemoveNoteFromCasePattern,
        event_class=RemoveNoteFromCaseReceivedEvent,
        use_case_class=RemoveNoteFromCaseReceivedUseCase,
        phrase="{actor} removed a note from the case",
        include_activity=True,
        occasions=(
            Occasion(
                when=(
                    "a note's author or the Case Owner withdraws a note from "
                    "the case"
                ),
                anchor="remove-note-from-case",
                heading="Remove note from case",
                description=(
                    "Removes the note from the case named by the target."
                ),
                example="remove_note_from_case",
                howto=HowToGuide.STATUS_UPDATES,
                shorthand=ProtocolShorthand.GI,
            ),
        ),
        page=MessagePage.GENERAL,
    ),
]
