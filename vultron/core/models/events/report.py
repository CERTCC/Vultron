"""Per-semantic inbound domain event types for vulnerability report activities."""

from typing import Literal

from vultron.core.models.activity import VultronActivity
from vultron.core.models.events._mixins import (
    _InnerObjectIsReportMixin,
    _ObjectIsOfferMixin,
    _ObjectIsReportMixin,
)
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.report import VultronReport


class CreateReportReceivedEvent(_ObjectIsReportMixin, VultronEvent):
    """Actor created a VulnerabilityReport."""

    semantic_type: Literal[MessageSemantics.CREATE_REPORT] = (
        MessageSemantics.CREATE_REPORT
    )
    report: VultronReport
    activity: VultronActivity


class SubmitReportReceivedEvent(_ObjectIsReportMixin, VultronEvent):
    """Actor submitted (offered) a VulnerabilityReport for validation."""

    semantic_type: Literal[MessageSemantics.SUBMIT_REPORT] = (
        MessageSemantics.SUBMIT_REPORT
    )
    report: VultronReport
    activity: VultronActivity


class ValidateReportReceivedEvent(
    _ObjectIsOfferMixin, _InnerObjectIsReportMixin, VultronEvent
):
    """Actor accepted an offer of a VulnerabilityReport, marking it as valid."""

    semantic_type: Literal[MessageSemantics.VALIDATE_REPORT] = (
        MessageSemantics.VALIDATE_REPORT
    )
    activity: VultronActivity


class InvalidateReportReceivedEvent(
    _ObjectIsOfferMixin, _InnerObjectIsReportMixin, VultronEvent
):
    """Actor tentatively rejected an offer of a VulnerabilityReport."""

    semantic_type: Literal[MessageSemantics.INVALIDATE_REPORT] = (
        MessageSemantics.INVALIDATE_REPORT
    )
    activity: VultronActivity


class AckReportReceivedEvent(
    _ObjectIsOfferMixin, _InnerObjectIsReportMixin, VultronEvent
):
    """Actor acknowledged (read) a VulnerabilityReport submission."""

    semantic_type: Literal[MessageSemantics.ACK_REPORT] = (
        MessageSemantics.ACK_REPORT
    )
    activity: VultronActivity


class CloseReportReceivedEvent(
    _ObjectIsOfferMixin, _InnerObjectIsReportMixin, VultronEvent
):
    """Actor rejected an offer of a VulnerabilityReport, closing it."""

    semantic_type: Literal[MessageSemantics.CLOSE_REPORT] = (
        MessageSemantics.CLOSE_REPORT
    )
    activity: VultronActivity
