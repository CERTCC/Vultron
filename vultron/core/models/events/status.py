"""Per-semantic inbound domain event types for case and participant status activities."""

from typing import TYPE_CHECKING, Literal, cast

from vultron.core.models.events.base import MessageSemantics, VultronEvent

if TYPE_CHECKING:
    from vultron.core.models.case import VultronCase
    from vultron.core.models.case_status import VultronCaseStatus
    from vultron.core.models.participant import VultronParticipant
    from vultron.core.models.participant_status import VultronParticipantStatus
else:
    VultronCase = object
    VultronCaseStatus = object
    VultronParticipant = object
    VultronParticipantStatus = object


class CreateCaseStatusReceivedEvent(VultronEvent):
    """Actor created a CaseStatus record for a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.CREATE_CASE_STATUS] = (
        MessageSemantics.CREATE_CASE_STATUS
    )

    @property
    def status_id(self) -> str | None:
        return self.object_id

    @property
    def status(self) -> "VultronCaseStatus | VultronParticipantStatus | None":
        return cast(
            "VultronCaseStatus | VultronParticipantStatus | None", self.object_
        )


class AddCaseStatusToCaseReceivedEvent(VultronEvent):
    """Actor added a CaseStatus to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_CASE_STATUS_TO_CASE] = (
        MessageSemantics.ADD_CASE_STATUS_TO_CASE
    )

    @property
    def status_id(self) -> str | None:
        return self.object_id

    @property
    def status(self) -> "VultronCaseStatus | VultronParticipantStatus | None":
        return cast(
            "VultronCaseStatus | VultronParticipantStatus | None", self.object_
        )

    @property
    def case_id(self) -> str | None:
        return self.target_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.target)


class CreateParticipantStatusReceivedEvent(VultronEvent):
    """Actor created a ParticipantStatus record."""

    semantic_type: Literal[MessageSemantics.CREATE_PARTICIPANT_STATUS] = (
        MessageSemantics.CREATE_PARTICIPANT_STATUS
    )

    @property
    def status_id(self) -> str | None:
        return self.object_id

    @property
    def status(self) -> "VultronCaseStatus | VultronParticipantStatus | None":
        return cast(
            "VultronCaseStatus | VultronParticipantStatus | None", self.object_
        )


class AddParticipantStatusToParticipantReceivedEvent(VultronEvent):
    """Actor added a ParticipantStatus to a CaseParticipant."""

    semantic_type: Literal[
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
    ] = MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT

    @property
    def status_id(self) -> str | None:
        return self.object_id

    @property
    def status(self) -> "VultronCaseStatus | VultronParticipantStatus | None":
        return cast(
            "VultronCaseStatus | VultronParticipantStatus | None", self.object_
        )

    @property
    def participant_id(self) -> str | None:
        return self.target_id

    @property
    def participant(self) -> "VultronParticipant | None":
        return cast("VultronParticipant | None", self.target)
