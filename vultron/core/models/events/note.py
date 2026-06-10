"""Per-semantic inbound domain event types for note activities."""

from typing import TYPE_CHECKING, Literal, cast

from vultron.core.models.events.base import MessageSemantics, VultronEvent

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase as VultronCase
    from vultron.core.models.note import VultronNote
else:
    VultronCase = object
    VultronNote = object


class CreateNoteReceivedEvent(VultronEvent):
    """Actor created a Note."""

    semantic_type: Literal[MessageSemantics.CREATE_NOTE] = (
        MessageSemantics.CREATE_NOTE
    )

    @property
    def note_id(self) -> str | None:
        return self.object_id

    @property
    def note(self) -> "VultronNote | None":
        return cast("VultronNote | None", self.object_)


class AddNoteToCaseReceivedEvent(VultronEvent):
    """Actor added a Note to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_NOTE_TO_CASE] = (
        MessageSemantics.ADD_NOTE_TO_CASE
    )

    @property
    def note_id(self) -> str | None:
        return self.object_id

    @property
    def note(self) -> "VultronNote | None":
        return cast("VultronNote | None", self.object_)

    @property
    def case_id(self) -> str | None:
        return self.target_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.target)


class RemoveNoteFromCaseReceivedEvent(VultronEvent):
    """Actor removed a Note from a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.REMOVE_NOTE_FROM_CASE] = (
        MessageSemantics.REMOVE_NOTE_FROM_CASE
    )

    @property
    def note_id(self) -> str | None:
        return self.object_id

    @property
    def note(self) -> "VultronNote | None":
        return cast("VultronNote | None", self.object_)

    @property
    def case_id(self) -> str | None:
        return self.target_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.target)
