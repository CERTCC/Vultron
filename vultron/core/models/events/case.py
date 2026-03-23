"""Per-semantic inbound domain event types for vulnerability case activities."""

from typing import Literal

from vultron.core.models.events._mixins import (
    _ObjectIsCaseMixin,
    _ObjectIsReportMixin,
    _TargetIsCaseMixin,
)
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.vultron_types import VultronActivity, VultronCase


class CreateCaseReceivedEvent(_ObjectIsCaseMixin, VultronEvent):
    """Actor created a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.CREATE_CASE] = (
        MessageSemantics.CREATE_CASE
    )
    case: VultronCase
    activity: VultronActivity


class UpdateCaseReceivedEvent(_ObjectIsCaseMixin, VultronEvent):
    """Actor updated a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.UPDATE_CASE] = (
        MessageSemantics.UPDATE_CASE
    )
    case: VultronCase


class EngageCaseReceivedEvent(_ObjectIsCaseMixin, VultronEvent):
    """Actor joined (engaged) a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ENGAGE_CASE] = (
        MessageSemantics.ENGAGE_CASE
    )


class DeferCaseReceivedEvent(_ObjectIsCaseMixin, VultronEvent):
    """Actor ignored (deferred) a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.DEFER_CASE] = (
        MessageSemantics.DEFER_CASE
    )


class AddReportToCaseReceivedEvent(
    _ObjectIsReportMixin, _TargetIsCaseMixin, VultronEvent
):
    """Actor added a VulnerabilityReport to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_REPORT_TO_CASE] = (
        MessageSemantics.ADD_REPORT_TO_CASE
    )


class CloseCaseReceivedEvent(_ObjectIsCaseMixin, VultronEvent):
    """Actor left (closed) a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.CLOSE_CASE] = (
        MessageSemantics.CLOSE_CASE
    )
