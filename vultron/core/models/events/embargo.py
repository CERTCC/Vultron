"""Per-semantic inbound domain event types for embargo activities."""

from typing import TYPE_CHECKING, Literal, cast

from vultron.core.models.activity import VultronActivity
from vultron.core.models.events.base import MessageSemantics, VultronEvent

if TYPE_CHECKING:
    from vultron.core.models.case import VultronCase
    from vultron.core.models.embargo_event import (
        EmbargoEvent as VultronEmbargoEvent,
    )
else:
    VultronCase = object
    VultronEmbargoEvent = object


class CreateEmbargoEventReceivedEvent(VultronEvent):
    """Actor created an EmbargoEvent."""

    semantic_type: Literal[MessageSemantics.CREATE_EMBARGO_EVENT] = (
        MessageSemantics.CREATE_EMBARGO_EVENT
    )

    @property
    def embargo_id(self) -> str | None:
        return self.object_id

    @property
    def embargo(self) -> "VultronEmbargoEvent | None":
        return cast("VultronEmbargoEvent | None", self.object_)


class AddEmbargoEventToCaseReceivedEvent(VultronEvent):
    """Actor added an EmbargoEvent to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE] = (
        MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE
    )

    @property
    def embargo_id(self) -> str | None:
        return self.object_id

    @property
    def embargo(self) -> "VultronEmbargoEvent | None":
        return cast("VultronEmbargoEvent | None", self.object_)

    @property
    def case_id(self) -> str | None:
        return self.target_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.target)


class RemoveEmbargoEventFromCaseReceivedEvent(VultronEvent):
    """Actor removed an EmbargoEvent from a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE] = (
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE
    )

    @property
    def embargo_id(self) -> str | None:
        return self.object_id

    @property
    def embargo(self) -> "VultronEmbargoEvent | None":
        return cast("VultronEmbargoEvent | None", self.object_)

    @property
    def case_id(self) -> str | None:
        return self.origin_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.origin)


class AnnounceEmbargoEventToCaseReceivedEvent(VultronEvent):
    """Actor announced an EmbargoEvent to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE] = (
        MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE
    )

    @property
    def case_id(self) -> str | None:
        return self.context_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.context)


class InviteToEmbargoOnCaseReceivedEvent(VultronEvent):
    """Actor invited another actor to join an embargo on a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.INVITE_TO_EMBARGO_ON_CASE] = (
        MessageSemantics.INVITE_TO_EMBARGO_ON_CASE
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]


class AcceptInviteToEmbargoOnCaseReceivedEvent(VultronEvent):
    """Actor accepted an invitation to join an embargo on a VulnerabilityCase."""

    semantic_type: Literal[
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE
    ] = MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE

    @property
    def invite_id(self) -> str | None:
        return self.object_id

    @property
    def invite(self) -> "VultronActivity | None":
        return cast("VultronActivity | None", self.object_)

    @property
    def embargo_id(self) -> str | None:
        return self.inner_object_id

    @property
    def embargo(self) -> "VultronEmbargoEvent | None":
        return cast("VultronEmbargoEvent | None", self.inner_object)

    @property
    def case_id(self) -> str | None:
        return self.inner_context_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.inner_context)


class RejectInviteToEmbargoOnCaseReceivedEvent(VultronEvent):
    """Actor rejected an invitation to join an embargo on a VulnerabilityCase."""

    semantic_type: Literal[
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE
    ] = MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE

    @property
    def invite_id(self) -> str | None:
        return self.object_id

    @property
    def invite(self) -> "VultronActivity | None":
        return cast("VultronActivity | None", self.object_)
