"""Per-semantic inbound domain event types for vulnerability case activities."""

from typing import TYPE_CHECKING, Literal, cast

from vultron.core.models.activity import VultronActivity
from vultron.core.models.events.base import MessageSemantics, VultronEvent

if TYPE_CHECKING:
    from vultron.core.models.case import VultronCase
    from vultron.core.models.report import VultronReport
else:
    VultronCase = object
    VultronReport = object


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
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.object_)


class UpdateCaseReceivedEvent(VultronEvent):
    """Actor updated a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.UPDATE_CASE] = (
        MessageSemantics.UPDATE_CASE
    )

    @property
    def case_id(self) -> str | None:
        return self.object_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.object_)


class EngageCaseReceivedEvent(VultronEvent):
    """Actor joined (engaged) a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ENGAGE_CASE] = (
        MessageSemantics.ENGAGE_CASE
    )

    @property
    def case_id(self) -> str | None:
        return self.object_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.object_)


class DeferCaseReceivedEvent(VultronEvent):
    """Actor ignored (deferred) a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.DEFER_CASE] = (
        MessageSemantics.DEFER_CASE
    )

    @property
    def case_id(self) -> str | None:
        return self.object_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.object_)


class AddReportToCaseReceivedEvent(VultronEvent):
    """Actor added a VulnerabilityReport to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_REPORT_TO_CASE] = (
        MessageSemantics.ADD_REPORT_TO_CASE
    )

    @property
    def report_id(self) -> str | None:
        return self.object_id

    @property
    def report(self) -> "VultronReport | None":
        return cast("VultronReport | None", self.object_)

    @property
    def case_id(self) -> str | None:
        return self.target_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.target)


class CloseCaseReceivedEvent(VultronEvent):
    """Actor left (closed) a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.CLOSE_CASE] = (
        MessageSemantics.CLOSE_CASE
    )

    @property
    def case_id(self) -> str | None:
        return self.object_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.object_)
