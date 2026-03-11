"""Per-semantic inbound domain event types for vulnerability case activities."""

from typing import Literal

from vultron.core.models.events.base import MessageSemantics, VultronEvent


class CreateCaseReceivedEvent(VultronEvent):
    """Actor created a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.CREATE_CASE] = (
        MessageSemantics.CREATE_CASE
    )


class UpdateCaseReceivedEvent(VultronEvent):
    """Actor updated a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.UPDATE_CASE] = (
        MessageSemantics.UPDATE_CASE
    )


class EngageCaseReceivedEvent(VultronEvent):
    """Actor joined (engaged) a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ENGAGE_CASE] = (
        MessageSemantics.ENGAGE_CASE
    )


class DeferCaseReceivedEvent(VultronEvent):
    """Actor ignored (deferred) a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.DEFER_CASE] = (
        MessageSemantics.DEFER_CASE
    )


class AddReportToCaseReceivedEvent(VultronEvent):
    """Actor added a VulnerabilityReport to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_REPORT_TO_CASE] = (
        MessageSemantics.ADD_REPORT_TO_CASE
    )


class CloseCaseReceivedEvent(VultronEvent):
    """Actor left (closed) a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.CLOSE_CASE] = (
        MessageSemantics.CLOSE_CASE
    )
