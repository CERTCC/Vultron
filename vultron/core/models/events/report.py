"""Per-semantic inbound domain event types for vulnerability report activities."""

from typing import TYPE_CHECKING, Literal, cast

from pydantic import model_validator

from vultron.core.models.events.base import MessageSemantics, VultronEvent

if TYPE_CHECKING:
    from vultron.core.models.activity import VultronActivity
    from vultron.core.models.report import VultronReport
else:
    VultronActivity = object
    VultronReport = object


class CreateReportReceivedEvent(VultronEvent):
    """Actor created a VulnerabilityReport."""

    semantic_type: Literal[MessageSemantics.CREATE_REPORT] = (
        MessageSemantics.CREATE_REPORT
    )

    @property
    def report_id(self) -> str | None:
        return self.object_id

    @property
    def report(self) -> "VultronReport | None":
        return cast("VultronReport | None", self.object_)


class SubmitReportReceivedEvent(VultronEvent):
    """Actor submitted (offered) a VulnerabilityReport for validation."""

    semantic_type: Literal[MessageSemantics.SUBMIT_REPORT] = (
        MessageSemantics.SUBMIT_REPORT
    )

    @property
    def report_id(self) -> str | None:
        return self.object_id

    @property
    def report(self) -> "VultronReport | None":
        return cast("VultronReport | None", self.object_)


class ValidateReportReceivedEvent(VultronEvent):
    """Actor accepted an offer of a VulnerabilityReport, marking it as valid."""

    semantic_type: Literal[MessageSemantics.VALIDATE_REPORT] = (
        MessageSemantics.VALIDATE_REPORT
    )

    @property
    def offer_id(self) -> str | None:
        return self.object_id

    @property
    def offer(self) -> "VultronActivity | None":
        return cast("VultronActivity | None", self.object_)

    @property
    def report_id(self) -> str | None:
        return self.inner_object_id

    @property
    def report(self) -> "VultronReport | None":
        return cast("VultronReport | None", self.inner_object)

    @model_validator(mode="after")
    def _require_offer_and_report_ids(self) -> "ValidateReportReceivedEvent":
        if self.offer_id is None:
            raise ValueError(
                "ValidateReportReceivedEvent requires offer_id "
                "(object_ must reference a non-None VultronActivity)"
            )
        if self.report_id is None:
            raise ValueError(
                "ValidateReportReceivedEvent requires report_id "
                "(inner_object must reference a non-None VulnerabilityReport)"
            )
        return self


class InvalidateReportReceivedEvent(VultronEvent):
    """Actor tentatively rejected an offer of a VulnerabilityReport."""

    semantic_type: Literal[MessageSemantics.INVALIDATE_REPORT] = (
        MessageSemantics.INVALIDATE_REPORT
    )

    @property
    def offer_id(self) -> str | None:
        return self.object_id

    @property
    def offer(self) -> "VultronActivity | None":
        return cast("VultronActivity | None", self.object_)

    @property
    def report_id(self) -> str | None:
        return self.inner_object_id

    @property
    def report(self) -> "VultronReport | None":
        return cast("VultronReport | None", self.inner_object)


class AckReportReceivedEvent(VultronEvent):
    """Actor acknowledged (read) a VulnerabilityReport submission."""

    semantic_type: Literal[MessageSemantics.ACK_REPORT] = (
        MessageSemantics.ACK_REPORT
    )

    @property
    def offer_id(self) -> str | None:
        return self.object_id

    @property
    def offer(self) -> "VultronActivity | None":
        return cast("VultronActivity | None", self.object_)

    @property
    def report_id(self) -> str | None:
        return self.inner_object_id

    @property
    def report(self) -> "VultronReport | None":
        return cast("VultronReport | None", self.inner_object)


class CloseReportReceivedEvent(VultronEvent):
    """Actor rejected an offer of a VulnerabilityReport, closing it."""

    semantic_type: Literal[MessageSemantics.CLOSE_REPORT] = (
        MessageSemantics.CLOSE_REPORT
    )

    @property
    def offer_id(self) -> str | None:
        return self.object_id

    @property
    def offer(self) -> "VultronActivity | None":
        return cast("VultronActivity | None", self.object_)

    @property
    def report_id(self) -> str | None:
        return self.inner_object_id

    @property
    def report(self) -> "VultronReport | None":
        return cast("VultronReport | None", self.inner_object)
