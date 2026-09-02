"""Per-semantic inbound domain event types for embargo activities."""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal, cast

from pydantic import field_validator

from vultron.core.models.activity import VultronActivity
from vultron.core.models.events.base import MessageSemantics, VultronEvent

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase as VultronCase
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
    rsvp_deadline: datetime | None = None

    @field_validator("rsvp_deadline", mode="before")
    @classmethod
    def _validate_rsvp_deadline(cls, v: object) -> datetime | None:
        if v is None:
            return None
        if not isinstance(v, datetime):
            raise ValueError(
                f"rsvp_deadline must be a datetime, got {type(v).__name__}"
            )
        if v.tzinfo is None:
            raise ValueError(
                "rsvp_deadline must be timezone-aware"
                " (naive datetime rejected per EP-07-002)"
            )
        return v.astimezone(timezone.utc)

    @property
    def case_id(self) -> str | None:
        return self.context_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.context)

    @property
    def to_recipients(self) -> list[str]:
        """The activity's ``to:`` addressees, in declaration order.

        Falsy entries are dropped.  An empty list means the activity carries
        no recipient at all, which is an OX-08-001 violation upstream.
        """
        return [recipient for recipient in self.activity.to or [] if recipient]

    @property
    def invitee_id(self) -> str | None:
        """The sole actor being invited to the embargo, when there is one.

        This is a *different* question from ``receiving_actor_id``, which is
        the actor whose replica the message is being applied to.  Per ADR-0022
        the invitee is leaf-node data threaded into the tree, never the BT's
        execution identity, so it MUST be read from the message rather than
        inferred from which store the message landed in.

        Returns ``None`` in two cases, and callers MUST NOT quietly substitute
        another identity in either:

        * no ``to:`` recipient at all — an OX-08-001 violation upstream;
        * more than one ``to:`` recipient — with several addressees the
          invitee is *replica-relative*, so only the receiving side can say
          which one this store is applying the invitation to.  Picking the
          first would give every recipient after the first a PEC transition
          and RSVP deadline on someone else's record (CM-28-001, CM-28-003).

        Received-side callers should therefore use
        ``vultron.core.use_cases.received.embargo.resolve_invitee_id()``,
        which resolves the multi-recipient case by addressee membership.

        Note this is *not* the same derivation as
        ``AcceptInviteActorToCaseReceivedEvent.invitee_id``, which reads the
        accepted Invite's ``object`` (``inner_object_id``).  An
        ``Invite(EmbargoEvent, Case)`` carries the embargo as its ``object``
        and the case as its ``context``, so ``to:`` is the only place the
        invited actor appears.
        """
        recipients = self.to_recipients
        if len(recipients) == 1:
            return recipients[0]
        return None


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
