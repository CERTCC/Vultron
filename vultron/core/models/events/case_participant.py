"""Per-semantic inbound domain event types for case participant activities."""

from typing import TYPE_CHECKING, Literal, cast

from vultron.core.models.events.base import (
    LedgerPositionedEvent,
    MessageSemantics,
)

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.models.case_participant import CaseParticipant
else:
    VulnerabilityCase = object
    CaseParticipant = object


class AddCaseParticipantToCaseReceivedEvent(LedgerPositionedEvent):
    """Actor added a CaseParticipant to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE] = (
        MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE
    )

    @property
    def participant_id(self) -> str | None:
        return self.object_id

    @property
    def participant(self) -> "CaseParticipant | None":
        return cast("CaseParticipant | None", self.object_)

    @property
    def case_id(self) -> str | None:
        return self.target_id

    @property
    def case(self) -> "VulnerabilityCase | None":
        return cast("VulnerabilityCase | None", self.target)


class RemoveCaseParticipantFromCaseReceivedEvent(LedgerPositionedEvent):
    """Actor removed a CaseParticipant from a VulnerabilityCase."""

    semantic_type: Literal[
        MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE
    ] = MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE

    @property
    def participant_id(self) -> str | None:
        return self.object_id

    @property
    def participant(self) -> "CaseParticipant | None":
        return cast("CaseParticipant | None", self.object_)

    @property
    def case_id(self) -> str | None:
        return self.target_id

    @property
    def case(self) -> "VulnerabilityCase | None":
        return cast("VulnerabilityCase | None", self.target)


class CreateCaseParticipantReceivedEvent(LedgerPositionedEvent):
    """The CASE_MANAGER created a participant record (ADR-0114, CLP-07-013).

    ``Create(CaseParticipant)``: the CASE_MANAGER's own act, committed as its
    ``create_case_participant`` ledger entry.  No received use case handles
    it: a participant takes the record from the committed entry (ADR-0140
    item 5).
    """

    semantic_type: Literal[MessageSemantics.CREATE_CASE_PARTICIPANT] = (
        MessageSemantics.CREATE_CASE_PARTICIPANT
    )

    @property
    def participant_id(self) -> str | None:
        return self.object_id

    @property
    def case_id(self) -> str | None:
        return self.context_id


class UpdateCaseParticipantReceivedEvent(LedgerPositionedEvent):
    """The CASE_MANAGER changed a participant record (CLP-07-013).

    ``Update(CaseParticipant)``: the CASE_MANAGER's own act, such as a
    ``CASE_OWNER`` role moving on an ownership transfer, committed as its
    ``update_case_participant`` ledger entry.  No received use case handles
    it (ADR-0140 item 5).
    """

    semantic_type: Literal[MessageSemantics.UPDATE_CASE_PARTICIPANT] = (
        MessageSemantics.UPDATE_CASE_PARTICIPANT
    )

    @property
    def participant_id(self) -> str | None:
        return self.object_id

    @property
    def case_id(self) -> str | None:
        return self.context_id
