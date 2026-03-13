"""Per-semantic inbound domain event types for note activities."""

from typing import Literal

from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.vultron_types import VultronNote


class CreateNoteReceivedEvent(VultronEvent):
    """Actor created a Note."""

    semantic_type: Literal[MessageSemantics.CREATE_NOTE] = (
        MessageSemantics.CREATE_NOTE
    )
    note: VultronNote | None = None


class AddNoteToCaseReceivedEvent(VultronEvent):
    """Actor added a Note to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_NOTE_TO_CASE] = (
        MessageSemantics.ADD_NOTE_TO_CASE
    )


class RemoveNoteFromCaseReceivedEvent(VultronEvent):
    """Actor removed a Note from a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.REMOVE_NOTE_FROM_CASE] = (
        MessageSemantics.REMOVE_NOTE_FROM_CASE
    )
