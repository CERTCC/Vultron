"""Per-semantic inbound domain event types for case participant activities."""

from typing import TYPE_CHECKING, Literal, cast

from vultron.core.models.events.base import (
    LedgerPositionedEvent,
    MessageSemantics,
)

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase
else:
    VulnerabilityCase = object


class RemoveParticipantFromCaseReceivedEvent(LedgerPositionedEvent):
    """The Case Owner removes an actor from active participation (CM-31-004).

    ``Remove(<Actor>, origin=<case>)``: the Case Owner's own act, sent to the
    CASE_MANAGER only, naming the actor as a typed reference rather than its
    ``CaseParticipant`` (ADR-0199).  The case has one record per actor, so
    the actor identifies the record (CM-19-003).
    """

    semantic_type: Literal[MessageSemantics.REMOVE_PARTICIPANT_FROM_CASE] = (
        MessageSemantics.REMOVE_PARTICIPANT_FROM_CASE
    )

    @property
    def participant_actor_id(self) -> str | None:
        """The actor the removal names (its ``object``)."""
        return self.object_id

    @property
    def case_id(self) -> str | None:
        """The case: a ``Remove`` names it in ``origin`` (VOC Remove)."""
        return self.origin_id

    @property
    def case(self) -> VulnerabilityCase | None:
        return cast("VulnerabilityCase | None", self.origin)


class ReinstateParticipantInCaseReceivedEvent(LedgerPositionedEvent):
    """The Case Owner reinstates a removed actor (CM-31-011).

    ``Add(<Actor>, target=<case>)``: the Case Owner's own act, sent to the
    CASE_MANAGER only, naming the actor as a typed reference rather than its
    ``CaseParticipant`` (ADR-0199).
    """

    semantic_type: Literal[MessageSemantics.REINSTATE_PARTICIPANT_IN_CASE] = (
        MessageSemantics.REINSTATE_PARTICIPANT_IN_CASE
    )

    @property
    def participant_actor_id(self) -> str | None:
        """The actor the reinstatement names (its ``object``)."""
        return self.object_id

    @property
    def case_id(self) -> str | None:
        return self.target_id

    @property
    def case(self) -> VulnerabilityCase | None:
        return cast("VulnerabilityCase | None", self.target)


class AnnounceAdmittedActReceivedEvent(LedgerPositionedEvent):
    """The CASE_MANAGER announces an act it admitted (ADR-0199).

    ``Announce(<the admitted act>)``, with the case as ``context``: sent to an
    actor the act concerns that the entry's fan-out does not reach, such as a
    removed or reinstated participant.  It informs and asks nothing, and a
    replica takes the change from the ledger entry, never from it
    (CM-31-029, CM-31-045).
    """

    semantic_type: Literal[MessageSemantics.ANNOUNCE_ADMITTED_ACT] = (
        MessageSemantics.ANNOUNCE_ADMITTED_ACT
    )

    @property
    def admitted_act_id(self) -> str | None:
        """The announced act (its ``object``)."""
        return self.object_id

    @property
    def case_id(self) -> str | None:
        return self.context_id


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
