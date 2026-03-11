"""Per-semantic inbound domain event types for embargo activities."""

from typing import Literal

from vultron.core.models.events.base import MessageSemantics, VultronEvent


class CreateEmbargoEventReceivedEvent(VultronEvent):
    """Actor created an EmbargoEvent."""

    semantic_type: Literal[MessageSemantics.CREATE_EMBARGO_EVENT] = (
        MessageSemantics.CREATE_EMBARGO_EVENT
    )


class AddEmbargoEventToCaseReceivedEvent(VultronEvent):
    """Actor added an EmbargoEvent to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE] = (
        MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE
    )


class RemoveEmbargoEventFromCaseReceivedEvent(VultronEvent):
    """Actor removed an EmbargoEvent from a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE] = (
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE
    )


class AnnounceEmbargoEventToCaseReceivedEvent(VultronEvent):
    """Actor announced an EmbargoEvent to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE] = (
        MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE
    )


class InviteToEmbargoOnCaseReceivedEvent(VultronEvent):
    """Actor invited another actor to join an embargo on a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.INVITE_TO_EMBARGO_ON_CASE] = (
        MessageSemantics.INVITE_TO_EMBARGO_ON_CASE
    )


class AcceptInviteToEmbargoOnCaseReceivedEvent(VultronEvent):
    """Actor accepted an invitation to join an embargo on a VulnerabilityCase."""

    semantic_type: Literal[
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE
    ] = MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE


class RejectInviteToEmbargoOnCaseReceivedEvent(VultronEvent):
    """Actor rejected an invitation to join an embargo on a VulnerabilityCase."""

    semantic_type: Literal[
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE
    ] = MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE
