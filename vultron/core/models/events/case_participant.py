"""Per-semantic inbound domain event types for case participant activities."""

from typing import TYPE_CHECKING, Literal, cast

from vultron.core.models.events.base import MessageSemantics, VultronEvent

if TYPE_CHECKING:
    from vultron.core.models.case import VultronCase
    from vultron.core.models.participant import VultronParticipant
else:
    VultronCase = object
    VultronParticipant = object


class CreateCaseParticipantReceivedEvent(VultronEvent):
    """Actor created a CaseParticipant record within a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.CREATE_CASE_PARTICIPANT] = (
        MessageSemantics.CREATE_CASE_PARTICIPANT
    )

    @property
    def participant_id(self) -> str | None:
        return self.object_id

    @property
    def participant(self) -> "VultronParticipant | None":
        return cast("VultronParticipant | None", self.object_)


class AddCaseParticipantToCaseReceivedEvent(VultronEvent):
    """Actor added a CaseParticipant to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE] = (
        MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE
    )

    @property
    def participant_id(self) -> str | None:
        return self.object_id

    @property
    def participant(self) -> "VultronParticipant | None":
        return cast("VultronParticipant | None", self.object_)

    @property
    def case_id(self) -> str | None:
        return self.target_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.target)


class RemoveCaseParticipantFromCaseReceivedEvent(VultronEvent):
    """Actor removed a CaseParticipant from a VulnerabilityCase."""

    semantic_type: Literal[
        MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE
    ] = MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE

    @property
    def participant_id(self) -> str | None:
        return self.object_id

    @property
    def participant(self) -> "VultronParticipant | None":
        return cast("VultronParticipant | None", self.object_)

    @property
    def case_id(self) -> str | None:
        return self.target_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.target)
