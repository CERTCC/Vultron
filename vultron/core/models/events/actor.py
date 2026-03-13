"""Per-semantic inbound domain event types for actor / case-membership activities.

Covers suggest-actor, ownership-transfer, and invite-actor-to-case semantics.
"""

from typing import Literal

from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.vultron_types import VultronActivity


class SuggestActorToCaseReceivedEvent(VultronEvent):
    """Actor offered another actor as a participant in a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.SUGGEST_ACTOR_TO_CASE] = (
        MessageSemantics.SUGGEST_ACTOR_TO_CASE
    )
    activity: VultronActivity | None = None


class AcceptSuggestActorToCaseReceivedEvent(VultronEvent):
    """Actor accepted a suggestion to add another actor to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE] = (
        MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE
    )
    activity: VultronActivity | None = None


class RejectSuggestActorToCaseReceivedEvent(VultronEvent):
    """Actor rejected a suggestion to add another actor to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE] = (
        MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE
    )


class OfferCaseOwnershipTransferReceivedEvent(VultronEvent):
    """Actor offered ownership of a VulnerabilityCase to another actor."""

    semantic_type: Literal[MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER] = (
        MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER
    )
    activity: VultronActivity | None = None


class AcceptCaseOwnershipTransferReceivedEvent(VultronEvent):
    """Actor accepted an offer to take ownership of a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER] = (
        MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER
    )


class RejectCaseOwnershipTransferReceivedEvent(VultronEvent):
    """Actor rejected an offer to take ownership of a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER] = (
        MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER
    )


class InviteActorToCaseReceivedEvent(VultronEvent):
    """Actor invited another actor to join a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.INVITE_ACTOR_TO_CASE] = (
        MessageSemantics.INVITE_ACTOR_TO_CASE
    )
    activity: VultronActivity | None = None


class AcceptInviteActorToCaseReceivedEvent(VultronEvent):
    """Actor accepted an invitation to join a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE] = (
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE
    )


class RejectInviteActorToCaseReceivedEvent(VultronEvent):
    """Actor rejected an invitation to join a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE] = (
        MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE
    )
