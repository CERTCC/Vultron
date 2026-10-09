"""Per-semantic inbound domain event types for embargo activities."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, cast

from pydantic import field_validator

from vultron.core.models.activity import VultronActivity
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.predicates.addressing import normalise_actor_id

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.models.embargo_event import EmbargoEvent
else:
    VulnerabilityCase = object
    EmbargoEvent = object


class CreateEmbargoEventReceivedEvent(VultronEvent):
    """Actor created an EmbargoEvent."""

    semantic_type: Literal[MessageSemantics.CREATE_EMBARGO_EVENT] = (
        MessageSemantics.CREATE_EMBARGO_EVENT
    )

    @property
    def embargo_id(self) -> str | None:
        return self.object_id

    @property
    def embargo(self) -> "EmbargoEvent | None":
        return cast("EmbargoEvent | None", self.object_)


class _OwnerEmbargoDecisionEvent(VultronEvent):
    """The case owner's decision on an embargo proposal (ADR-0122).

    ``Accept`` or ``Reject`` of the ``EmbargoEvent`` itself, with the case
    as ``target`` — not of the ``Invite`` that proposed it, which is each
    sender's own consent.
    """

    @property
    def embargo_id(self) -> str | None:
        return self.object_id

    @property
    def embargo(self) -> "EmbargoEvent | None":
        return cast("EmbargoEvent | None", self.object_)

    @property
    def case_id(self) -> str | None:
        return self.target_id

    @property
    def case(self) -> "VulnerabilityCase | None":
        return cast("VulnerabilityCase | None", self.target)


class ActivateEmbargoOnCaseReceivedEvent(_OwnerEmbargoDecisionEvent):
    """The case owner activated a proposed embargo on the case.

    ``Accept(EmbargoEvent, target=VulnerabilityCase)`` (ADR-0122).
    """

    semantic_type: Literal[MessageSemantics.ACTIVATE_EMBARGO_ON_CASE] = (
        MessageSemantics.ACTIVATE_EMBARGO_ON_CASE
    )


class RejectEmbargoProposalOnCaseReceivedEvent(_OwnerEmbargoDecisionEvent):
    """The case owner rejected a proposed embargo on the case.

    ``Reject(EmbargoEvent, target=VulnerabilityCase)`` (ADR-0122).
    """

    semantic_type: Literal[
        MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE
    ] = MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE


class RemoveEmbargoEventFromCaseReceivedEvent(VultronEvent):
    """Actor removed an EmbargoEvent from a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE] = (
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE
    )

    @property
    def embargo_id(self) -> str | None:
        return self.object_id

    @property
    def embargo(self) -> "EmbargoEvent | None":
        return cast("EmbargoEvent | None", self.object_)

    @property
    def case_id(self) -> str | None:
        return self.origin_id

    @property
    def case(self) -> "VulnerabilityCase | None":
        return cast("VulnerabilityCase | None", self.origin)


class AnnounceEmbargoEventToCaseReceivedEvent(VultronEvent):
    """Actor announced an EmbargoEvent to a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE] = (
        MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE
    )

    @property
    def embargo_id(self) -> str | None:
        return self.object_id

    @property
    def embargo(self) -> "EmbargoEvent | None":
        return cast("EmbargoEvent | None", self.object_)

    @property
    def case_id(self) -> str | None:
        return self.context_id

    @property
    def case(self) -> "VulnerabilityCase | None":
        return cast("VulnerabilityCase | None", self.context)


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
            raise ValueError(  # noqa: TRY004  # ruff-baseline #3353
                f"rsvp_deadline must be a datetime, got {type(v).__name__}"
            )
        if v.tzinfo is None:
            raise ValueError(
                "rsvp_deadline must be timezone-aware"
                " (naive datetime rejected per EP-07-002)"
            )
        return v.astimezone(UTC)

    @property
    def case_id(self) -> str | None:
        return self.context_id

    @property
    def case(self) -> "VulnerabilityCase | None":
        return cast("VulnerabilityCase | None", self.context)

    @property
    def to_recipients(self) -> list[str]:
        """The activity's distinct ``to:`` addressees, in declaration order.

        Each is given in its canonical spelling (no trailing slash, #2667),
        and two entries naming the same actor count once, so ``[X, X + "/"]``
        is one recipient, not two.  Falsy entries are dropped.  An empty list
        means the activity carries no recipient at all, which is an OX-08-001
        violation upstream.
        """
        canonical = (
            normalise_actor_id(recipient)
            for recipient in self.activity.to or []
            if recipient
        )
        return list(dict.fromkeys(canonical))

    @property
    def invitee_id(self) -> str | None:
        """The Invite's sole distinct ``to`` recipient; ``None`` otherwise.

        The invitee of an ``Invite(EmbargoEvent)`` is its sole ``to``
        recipient (EP-09-010).  This is a *different* question from
        ``receiving_actor_id``, the actor whose replica the message is being
        applied to: per ADR-0022 the invitee is leaf-node data read from the
        message, never inferred from which store the message landed in.

        ``None`` means the Invite is a misrouting — no recipient (an
        OX-08-001 violation upstream) or several — and callers MUST NOT
        substitute another identity.  Received-side callers use
        ``vultron.core.use_cases.received.embargo.resolve_invitee_id()``,
        which refuses such an Invite with the recipient count.

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
    def embargo(self) -> "EmbargoEvent | None":
        return cast("EmbargoEvent | None", self.inner_object)

    @property
    def case_id(self) -> str | None:
        return self.inner_context_id

    @property
    def case(self) -> "VulnerabilityCase | None":
        return cast("VulnerabilityCase | None", self.inner_context)


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
    def embargo(self) -> "EmbargoEvent | None":
        return cast("EmbargoEvent | None", self.inner_object)

    @property
    def case_id(self) -> str | None:
        return self.inner_context_id

    @property
    def case(self) -> "VulnerabilityCase | None":
        return cast("VulnerabilityCase | None", self.inner_context)
