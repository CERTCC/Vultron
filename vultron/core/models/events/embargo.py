"""Per-semantic inbound domain event types for embargo activities."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, cast

from pydantic import field_validator, model_validator

from vultron.core.models.activity import VultronActivity
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    TerminationCause,
)
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.states.embargo_register import TerminationReason
from vultron.primitives import normalise_actor_id

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.models.embargo_event import EmbargoEvent
else:
    VulnerabilityCase = object
    EmbargoEvent = object


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


class WithdrawFromEmbargoOnCaseReceivedEvent(VultronEvent):
    """A participant withdrew from the embargo in force on the case.

    ``Leave(EmbargoEvent)[context=VulnerabilityCase]`` (MSM-07-010,
    ADR-0122): the sender ends its own consent to the active embargo.  It is
    not an answer to an Invite, and it ends nothing for the case.
    """

    semantic_type: Literal[MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE] = (
        MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE
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


class RemoveEmbargoEventFromCaseReceivedEvent(VultronEvent):
    """Actor removed an EmbargoEvent from a VulnerabilityCase.

    ``termination_reason`` is the termination's what, parsed from the
    ``Remove``'s ``content`` at the edge (ADR-0122, ADR-0032).
    ``termination_cause`` is its why, parsed from ``terminationCause``, or
    ``None`` when the sender named none (EMB-13-005).  The two fit each
    other: an ``END_TIME_REACHED`` termination has no cause.
    """

    semantic_type: Literal[MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE] = (
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE
    )
    termination_reason: TerminationReason
    termination_cause: TerminationCause | None = None

    @model_validator(mode="after")
    def _cause_fits_reason(self) -> "RemoveEmbargoEventFromCaseReceivedEvent":
        """Refuse a cause the what cannot have (EMB-13-004)."""
        EmbargoTermination.from_reason(
            self.termination_reason, self.termination_cause
        )
        return self

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


class UndoInviteToEmbargoOnCaseReceivedEvent(VultronEvent):
    """The CASE_MANAGER withdrew an embargo invitation it had sent (EMB-16-001).

    ``Undo(Invite(EmbargoEvent))``: an actor undoes only an activity it
    performed (ADR-0152), so the sender is the CASE_MANAGER that sent the
    Invite.  No received use case handles it: a participant learns the
    withdrawal from the committed entry (EP-09-007).
    """

    semantic_type: Literal[MessageSemantics.UNDO_INVITE_TO_EMBARGO_ON_CASE] = (
        MessageSemantics.UNDO_INVITE_TO_EMBARGO_ON_CASE
    )

    @property
    def invite_id(self) -> str | None:
        return self.object_id

    @property
    def embargo_id(self) -> str | None:
        return self.inner_object_id

    @property
    def case_id(self) -> str | None:
        return self.inner_context_id


class CreateEmbargoEventReceivedEvent(VultronEvent):
    """The CASE_MANAGER recorded an embargo its case's creation wrote.

    ``Create(EmbargoEvent)``: committed as the ``create_embargo_event``
    ledger entry right after the genesis entry, carrying the embargo in full
    (CLP-07-013).  No received use case handles it: a participant takes the
    embargo from the committed entry (ADR-0140 item 5).
    """

    semantic_type: Literal[MessageSemantics.CREATE_EMBARGO_EVENT] = (
        MessageSemantics.CREATE_EMBARGO_EVENT
    )

    @property
    def embargo_id(self) -> str | None:
        return self.object_id

    @property
    def case_id(self) -> str | None:
        return self.context_id


class CreateEmbargoConsentReceivedEvent(VultronEvent):
    """The CASE_MANAGER created a participant's consent row (ADR-0122).

    ``Create(EmbargoConsent)``: the CASE_MANAGER's own act, such as the
    ``UNINVITED`` row a proposal writes, committed as its
    ``create_embargo_consent`` ledger entry.  No received use case handles
    it: a participant takes the row from the committed entry (ADR-0140
    item 5).
    """

    semantic_type: Literal[MessageSemantics.CREATE_EMBARGO_CONSENT] = (
        MessageSemantics.CREATE_EMBARGO_CONSENT
    )

    @property
    def consent_id(self) -> str | None:
        return self.object_id

    @property
    def case_id(self) -> str | None:
        return self.context_id


class UpdateEmbargoConsentReceivedEvent(VultronEvent):
    """The CASE_MANAGER changed a participant's consent row (ADR-0122).

    ``Update(EmbargoConsent)``: the CASE_MANAGER's own act, such as a
    ``CARRY_OVER`` at activation, an invitation's time-out or a change of its
    own consent (MSM-07-004), committed as its ``update_embargo_consent``
    ledger entry.  No received use case handles it (ADR-0140 item 5).
    """

    semantic_type: Literal[MessageSemantics.UPDATE_EMBARGO_CONSENT] = (
        MessageSemantics.UPDATE_EMBARGO_CONSENT
    )

    @property
    def consent_id(self) -> str | None:
        return self.object_id

    @property
    def case_id(self) -> str | None:
        return self.context_id
