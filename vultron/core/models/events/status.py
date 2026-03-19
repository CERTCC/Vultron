"""Per-semantic inbound domain event types for case and participant status activities."""

from typing import Literal

from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.vultron_types import (
    VultronCaseStatus,
    VultronParticipantStatus,
)


class CreateCaseStatusReceivedEvent(VultronEvent):
    """Actor created a CaseStatus record for a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.CREATE_CASE_STATUS] = (
        MessageSemantics.CREATE_CASE_STATUS
    )
    status: VultronCaseStatus


class AddCaseStatusToCaseReceivedEvent(VultronEvent):
    """Actor added a CaseStatus to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_CASE_STATUS_TO_CASE] = (
        MessageSemantics.ADD_CASE_STATUS_TO_CASE
    )


class CreateParticipantStatusReceivedEvent(VultronEvent):
    """Actor created a ParticipantStatus record."""

    semantic_type: Literal[MessageSemantics.CREATE_PARTICIPANT_STATUS] = (
        MessageSemantics.CREATE_PARTICIPANT_STATUS
    )
    status: VultronParticipantStatus


class AddParticipantStatusToParticipantReceivedEvent(VultronEvent):
    """Actor added a ParticipantStatus to a CaseParticipant."""

    semantic_type: Literal[
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
    ] = MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
