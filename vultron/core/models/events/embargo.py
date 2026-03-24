"""Per-semantic inbound domain event types for embargo activities."""

from typing import Literal

from vultron.core.models.activity import VultronActivity
from vultron.core.models.events._mixins import (
    _ContextIsCaseMixin,
    _InnerContextIsCaseMixin,
    _InnerObjectIsEmbargoMixin,
    _ObjectIsEmbargoMixin,
    _ObjectIsInviteMixin,
    _OriginIsCaseMixin,
    _TargetIsCaseMixin,
)
from vultron.core.models.events.base import MessageSemantics, VultronEvent


class CreateEmbargoEventReceivedEvent(_ObjectIsEmbargoMixin, VultronEvent):
    """Actor created an EmbargoEvent."""

    semantic_type: Literal[MessageSemantics.CREATE_EMBARGO_EVENT] = (
        MessageSemantics.CREATE_EMBARGO_EVENT
    )


class AddEmbargoEventToCaseReceivedEvent(
    _ObjectIsEmbargoMixin, _TargetIsCaseMixin, VultronEvent
):
    """Actor added an EmbargoEvent to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE] = (
        MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE
    )


class RemoveEmbargoEventFromCaseReceivedEvent(
    _ObjectIsEmbargoMixin, _OriginIsCaseMixin, VultronEvent
):
    """Actor removed an EmbargoEvent from a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE] = (
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE
    )


class AnnounceEmbargoEventToCaseReceivedEvent(
    _ContextIsCaseMixin, VultronEvent
):
    """Actor announced an EmbargoEvent to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE] = (
        MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE
    )


class InviteToEmbargoOnCaseReceivedEvent(VultronEvent):
    """Actor invited another actor to join an embargo on a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.INVITE_TO_EMBARGO_ON_CASE] = (
        MessageSemantics.INVITE_TO_EMBARGO_ON_CASE
    )
    activity: VultronActivity


class AcceptInviteToEmbargoOnCaseReceivedEvent(
    _ObjectIsInviteMixin,
    _InnerObjectIsEmbargoMixin,
    _InnerContextIsCaseMixin,
    VultronEvent,
):
    """Actor accepted an invitation to join an embargo on a VulnerabilityCase."""

    semantic_type: Literal[
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE
    ] = MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE


class RejectInviteToEmbargoOnCaseReceivedEvent(
    _ObjectIsInviteMixin, VultronEvent
):
    """Actor rejected an invitation to join an embargo on a VulnerabilityCase."""

    semantic_type: Literal[
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE
    ] = MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE
