"""Per-semantic inbound domain event types for vulnerability report activities."""

from typing import TYPE_CHECKING, Literal, cast

from pydantic import Field, model_validator

from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.report_claims import ClaimsReading

if TYPE_CHECKING:
    from vultron.core.models.activity import VultronActivity
    from vultron.core.models.report import VulnerabilityReport
else:
    VultronActivity = object
    VulnerabilityReport = object


class CreateReportReceivedEvent(VultronEvent):
    """Actor created a VulnerabilityReport."""

    semantic_type: Literal[MessageSemantics.CREATE_REPORT] = (
        MessageSemantics.CREATE_REPORT
    )

    @property
    def report_id(self) -> str | None:
        return self.object_id

    @property
    def report(self) -> "VulnerabilityReport | None":
        return cast("VulnerabilityReport | None", self.object_)


class SubmitReportReceivedEvent(VultronEvent):
    """Actor submitted (offered) a VulnerabilityReport for validation.

    ``proposed_embargo`` is the Reporter's proposed terms for this report,
    when the Offer carried them (EP-04-004); its ``context`` is the report
    (EP-04-009).  Extraction surfaces it here so no use case re-reads the
    stored wire activity for it (ADR-0035, DL-06-002).

    ``claims_readings`` holds the wire edge's reading of each CSAF 2.1
    document among the report's attachments: its schema verdict and what it
    claims (CSAF-04-001, CSAF-04-003).  It is empty when the report carries
    none.  Reading a document never refuses the Offer (CSAF-02-006).
    """

    semantic_type: Literal[MessageSemantics.SUBMIT_REPORT] = (
        MessageSemantics.SUBMIT_REPORT
    )
    proposed_embargo: EmbargoEvent | None = None
    claims_readings: list[ClaimsReading] = Field(default_factory=list)

    @property
    def report_id(self) -> str | None:
        return self.object_id

    @property
    def report(self) -> "VulnerabilityReport | None":
        return cast("VulnerabilityReport | None", self.object_)


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
    def report(self) -> "VulnerabilityReport | None":
        return cast("VulnerabilityReport | None", self.inner_object)

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
    def report(self) -> "VulnerabilityReport | None":
        return cast("VulnerabilityReport | None", self.inner_object)


class AckReportReceivedEvent(VultronEvent):
    """Actor acknowledged receipt of a VulnerabilityReport submission."""

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
    def report(self) -> "VulnerabilityReport | None":
        return cast("VulnerabilityReport | None", self.inner_object)


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
    def report(self) -> "VulnerabilityReport | None":
        return cast("VulnerabilityReport | None", self.inner_object)
