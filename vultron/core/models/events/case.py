"""Per-semantic inbound domain event types for vulnerability case activities."""

from typing import TYPE_CHECKING, Literal, cast

from vultron.core.models.activity import VultronActivity
from vultron.core.models.events.base import (
    LedgerPositionedEvent,
    MessageSemantics,
    VultronEvent,
)

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.models.report import VulnerabilityReport
else:
    VulnerabilityCase = object
    VulnerabilityReport = object


class CreateCaseReceivedEvent(VultronEvent):
    """Actor created a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.CREATE_CASE] = (
        MessageSemantics.CREATE_CASE
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]

    @property
    def case_id(self) -> str | None:
        return self.object_id

    @property
    def case(self) -> "VulnerabilityCase | None":
        return cast("VulnerabilityCase | None", self.object_)


class EngageCaseReceivedEvent(LedgerPositionedEvent):
    """Actor joined (engaged) a VulnerabilityCase.

    The activity names the case by typed reference and carries no copy of
    it (ADR-0165), so the event offers only :attr:`case_id`: the receiver
    reads the case from its own store.
    """

    semantic_type: Literal[MessageSemantics.ENGAGE_CASE] = (
        MessageSemantics.ENGAGE_CASE
    )

    @property
    def case_id(self) -> str | None:
        return self.object_id


class DeferCaseReceivedEvent(LedgerPositionedEvent):
    """Actor ignored (deferred) a VulnerabilityCase.

    The activity names the case by typed reference and carries no copy of
    it (ADR-0165), so the event offers only :attr:`case_id`: the receiver
    reads the case from its own store.
    """

    semantic_type: Literal[MessageSemantics.DEFER_CASE] = (
        MessageSemantics.DEFER_CASE
    )

    @property
    def case_id(self) -> str | None:
        return self.object_id


class AddReportToCaseReceivedEvent(LedgerPositionedEvent):
    """Actor added a VulnerabilityReport to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_REPORT_TO_CASE] = (
        MessageSemantics.ADD_REPORT_TO_CASE
    )

    @property
    def report_id(self) -> str | None:
        return self.object_id

    @property
    def report(self) -> "VulnerabilityReport | None":
        return cast("VulnerabilityReport | None", self.object_)

    @property
    def case_id(self) -> str | None:
        return self.target_id

    @property
    def case(self) -> "VulnerabilityCase | None":
        return cast("VulnerabilityCase | None", self.target)


class CloseCaseReceivedEvent(LedgerPositionedEvent):
    """Actor left (closed) a VulnerabilityCase.

    The activity names the case by typed reference and carries no copy of
    it (ADR-0165), so the event offers only :attr:`case_id`: the receiver
    reads the case from its own store.
    """

    semantic_type: Literal[MessageSemantics.CLOSE_CASE] = (
        MessageSemantics.CLOSE_CASE
    )

    @property
    def case_id(self) -> str | None:
        return self.object_id


class UpdateCaseOwnerReceivedEvent(VultronEvent):
    """The CASE_MANAGER named a new Case Owner on the case (CM-21-002).

    ``Update(VulnerabilityCase)``: the CASE_MANAGER's own act on an ownership
    transfer, carrying the case with its new ``attributed_to``, committed as
    its ``update_case_owner`` ledger entry.  No received use case handles it
    (ADR-0140 item 5).
    """

    semantic_type: Literal[MessageSemantics.UPDATE_CASE_OWNER] = (
        MessageSemantics.UPDATE_CASE_OWNER
    )

    @property
    def case_id(self) -> str | None:
        return self.object_id

    @property
    def case(self) -> "VulnerabilityCase | None":
        return cast("VulnerabilityCase | None", self.object_)
