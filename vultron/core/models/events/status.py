"""Per-semantic inbound domain event types for case and participant status activities.

Each status ``Add`` names the history it extends in ``target`` and its case
in ``context`` (ADR-0204): ``Add(CaseStatus, target=<case>/statuses)`` and
``Add(ParticipantStatus, target=<participant>/statuses)``.
"""

from typing import TYPE_CHECKING, Literal, cast

from vultron.core.models.events.base import (
    LedgerPositionedEvent,
    MessageSemantics,
)
from vultron.core.models.status_history import (
    is_status_history_id,
    status_history_owner,
)

if TYPE_CHECKING:
    from vultron.core.models.case_status import CaseStatus
    from vultron.core.models.participant_status import ParticipantStatus
else:
    CaseStatus = object
    ParticipantStatus = object


def _history_owner(history_id: str | None) -> str | None:
    """The record whose status history *history_id* names, if it is one."""
    if history_id is None or not is_status_history_id(history_id):
        return None
    return status_history_owner(history_id)


class AddCaseStatusToCaseReceivedEvent(LedgerPositionedEvent):
    """Actor added a CaseStatus to the case's status history (ADR-0204)."""

    semantic_type: Literal[MessageSemantics.ADD_CASE_STATUS_TO_CASE] = (
        MessageSemantics.ADD_CASE_STATUS_TO_CASE
    )

    @property
    def status_id(self) -> str | None:
        return self.object_id

    @property
    def status(self) -> CaseStatus | ParticipantStatus | None:
        return cast("CaseStatus | ParticipantStatus | None", self.object_)

    @property
    def case_id(self) -> str | None:
        """The case the ``Add`` names in ``context``."""
        return self.context_id

    @property
    def history_owner_id(self) -> str | None:
        """The record whose status history ``target`` names, or ``None``.

        A well-formed ``Add(CaseStatus)`` names the history of its own
        ``context`` case, so this equals :attr:`case_id`.
        """
        return _history_owner(self.target_id)


class AddParticipantStatusToParticipantReceivedEvent(LedgerPositionedEvent):
    """Actor added a ParticipantStatus to a participant's status history."""

    semantic_type: Literal[
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
    ] = MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT

    @property
    def status_id(self) -> str | None:
        return self.object_id

    @property
    def status(self) -> CaseStatus | ParticipantStatus | None:
        return cast("CaseStatus | ParticipantStatus | None", self.object_)

    @property
    def participant_id(self) -> str | None:
        """The participant whose status history ``target`` names, or ``None``
        when ``target`` names no status history (ADR-0204)."""
        return _history_owner(self.target_id)

    @property
    def case_id(self) -> str | None:
        """The case the ``Add`` names in ``context`` (ADR-0204)."""
        return self.context_id
