"""Per-semantic inbound domain event types for case participant activities."""

from typing import Literal

from vultron.core.models.events._mixins import (
    _ObjectIsParticipantMixin,
    _TargetIsCaseMixin,
)
from vultron.core.models.events.base import MessageSemantics, VultronEvent


class CreateCaseParticipantReceivedEvent(
    _ObjectIsParticipantMixin, VultronEvent
):
    """Actor created a CaseParticipant record within a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.CREATE_CASE_PARTICIPANT] = (
        MessageSemantics.CREATE_CASE_PARTICIPANT
    )


class AddCaseParticipantToCaseReceivedEvent(
    _ObjectIsParticipantMixin, _TargetIsCaseMixin, VultronEvent
):
    """Actor added a CaseParticipant to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE] = (
        MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE
    )


class RemoveCaseParticipantFromCaseReceivedEvent(
    _ObjectIsParticipantMixin, _TargetIsCaseMixin, VultronEvent
):
    """Actor removed a CaseParticipant from a VulnerabilityCase."""

    semantic_type: Literal[
        MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE
    ] = MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE
