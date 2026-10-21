"""Per-semantic inbound domain event types for actor / case-membership activities.

Covers suggest-actor, ownership-transfer, and invite-actor-to-case semantics.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, cast

from pydantic import field_validator

from vultron.core.models._helpers import _as_id
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case_stub import stub_case_id
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.ledger_position import LedgerPosition
from vultron.primitives import normalise_actor_id

if TYPE_CHECKING:
    from vultron.core.models.base import CoreObject
    from vultron.core.models.case import VulnerabilityCase
else:
    CoreObject = object
    VulnerabilityCase = object


class OfferActorToCaseReceivedEvent(VultronEvent):
    """CaseActor received Offer(Actor, Case) from a recommending participant.

    Routed to the CaseActor inbox per ADR-0026/CM-16-001.
    """

    semantic_type: Literal[MessageSemantics.OFFER_ACTOR_TO_CASE] = (
        MessageSemantics.OFFER_ACTOR_TO_CASE
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]


class OfferCaseParticipantRoleReceivedEvent(VultronEvent):
    """Actor offered a CVDRole to a target Actor in a VulnerabilityCase context.

    Canonical ADR-0039 role-delegation wire format:
    ``Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)``.
    Replaces the deprecated ``OfferCaseManagerRoleReceivedEvent`` wire format.
    See SE-08-003, ADR-0039.
    """

    semantic_type: Literal[MessageSemantics.OFFER_CASE_PARTICIPANT_ROLE] = (
        MessageSemantics.OFFER_CASE_PARTICIPANT_ROLE
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]


class AcceptCaseParticipantRoleReceivedEvent(VultronEvent):
    """The CASE_MANAGER received Accept(Offer(CaseParticipantRole, ...)).

    The ADR-0039 canonical role-delegation acceptance: the target of the
    role offer accepted it, answering the CASE_MANAGER (CM-33-004).
    See SE-08-003, ADR-0039.
    """

    semantic_type: Literal[MessageSemantics.ACCEPT_CASE_PARTICIPANT_ROLE] = (
        MessageSemantics.ACCEPT_CASE_PARTICIPANT_ROLE
    )

    @property
    def offer_id(self) -> str | None:
        return self.object_id

    @property
    def offer(self) -> "VultronActivity | None":
        return cast("VultronActivity | None", self.object_)


class RejectCaseParticipantRoleReceivedEvent(VultronEvent):
    """The CASE_MANAGER received Reject(Offer(CaseParticipantRole, ...)).

    The ADR-0039 canonical role-delegation rejection: the target of the
    role offer declined it, answering the CASE_MANAGER (CM-33-004).
    See SE-08-003, ADR-0039.
    """

    semantic_type: Literal[MessageSemantics.REJECT_CASE_PARTICIPANT_ROLE] = (
        MessageSemantics.REJECT_CASE_PARTICIPANT_ROLE
    )

    @property
    def offer_id(self) -> str | None:
        return self.object_id

    @property
    def offer(self) -> "VultronActivity | None":
        return cast("VultronActivity | None", self.object_)


def _deadline_in_utc(v: datetime | None, field: str) -> datetime | None:
    """Hold an answer deadline in UTC (CM-21-016, CS-13-001).

    The wire edge already attached UTC to a naive value; an aware one in
    another offset is converted, so core compares and reports one zone.
    """
    if v is None:
        return None
    if v.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware (CM-21-016)")
    return v.astimezone(UTC)


class ProposeCaseOwnershipTransferReceivedEvent(VultronEvent):
    """The Case Owner proposed an ownership transfer to the CASE_MANAGER.

    ``Offer(Offer(VulnerabilityCase))`` with the case as its ``context``
    (ADR-0148).  The inner Offer is the template of the one the CASE_MANAGER
    makes: its object names the case, its ``target`` the transferee, and its
    ``end_time`` the deadline to answer.  The CASE_MANAGER takes only those
    three from it; the inner id, ``actor`` and ``to`` are the sender's and
    are ignored (CM-21-005).

    ``proposed_answer_deadline`` is the inner Offer's ``end_time``, normalised
    to UTC at the wire edge (CM-21-016); ``None`` when it carries none.
    """

    semantic_type: Literal[
        MessageSemantics.PROPOSE_CASE_OWNERSHIP_TRANSFER
    ] = MessageSemantics.PROPOSE_CASE_OWNERSHIP_TRANSFER
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]
    proposed_answer_deadline: datetime | None = None

    @field_validator("proposed_answer_deadline")
    @classmethod
    def _proposed_deadline_is_utc(cls, v: datetime | None) -> datetime | None:
        return _deadline_in_utc(v, "proposed_answer_deadline")

    @property
    def case_id(self) -> str | None:
        """The case the proposal is about: its ``context``."""
        return self.context_id

    @property
    def proposed_case_id(self) -> str | None:
        """The case the inner Offer names as its object."""
        return self.inner_object_id

    @property
    def transferee_id(self) -> str | None:
        """The actor the inner Offer names as its ``target``."""
        return self.inner_target_id


class OfferCaseOwnershipTransferReceivedEvent(VultronEvent):
    """The CASE_MANAGER offered ownership of a VulnerabilityCase to an actor.

    The one ``Offer(VulnerabilityCase)`` of a transfer, which the
    CASE_MANAGER makes on the Case Owner's behalf and the transferee answers
    (ADR-0148, CM-21-005).

    ``answer_deadline`` is the Offer's activity-level ``end_time``, the
    deadline to answer it (CM-21-016), normalised to UTC at the wire edge;
    ``None`` when the Offer carries none.
    """

    semantic_type: Literal[MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER] = (
        MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]
    answer_deadline: datetime | None = None

    @field_validator("answer_deadline")
    @classmethod
    def _answer_deadline_is_utc(cls, v: datetime | None) -> datetime | None:
        """Hold the deadline in UTC (CM-21-016, CS-13-001)."""
        return _deadline_in_utc(v, "answer_deadline")


class AcceptCaseOwnershipTransferReceivedEvent(VultronEvent):
    """Actor accepted an offer to take ownership of a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER] = (
        MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER
    )

    @property
    def case_id(self) -> str | None:
        return self.inner_object_id

    @property
    def case(self) -> "VulnerabilityCase | None":
        return cast("VulnerabilityCase | None", self.inner_object)


class RejectCaseOwnershipTransferReceivedEvent(VultronEvent):
    """Actor rejected an offer to take ownership of a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER] = (
        MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER
    )

    @property
    def offer_id(self) -> str | None:
        return self.object_id

    @property
    def offer(self) -> "VultronActivity | None":
        return cast("VultronActivity | None", self.object_)

    @property
    def case_id(self) -> str | None:
        """The case the declined Offer would have transferred."""
        return self.inner_object_id


class UndoCaseOwnershipTransferReceivedEvent(VultronEvent):
    """The Case Owner withdrew its ownership-transfer proposal.

    ``Undo(Offer(Offer(VulnerabilityCase)))``, sent by the Case Owner that
    made the proposal and addressed to the CASE_MANAGER, which withdraws the
    Offer it made from that proposal (CM-21-015, ADR-0148).
    """

    semantic_type: Literal[MessageSemantics.UNDO_CASE_OWNERSHIP_TRANSFER] = (
        MessageSemantics.UNDO_CASE_OWNERSHIP_TRANSFER
    )

    @property
    def proposal_id(self) -> str | None:
        """The proposal withdrawn."""
        return self.object_id

    @property
    def proposal(self) -> "VultronActivity | None":
        return cast("VultronActivity | None", self.object_)

    @property
    def case_id(self) -> str | None:
        """The case the withdrawn proposal names: the proposal's ``context``."""
        return self.inner_context_id

    @property
    def proposer_id(self) -> str:
        """The actor the withdrawn proposal names as its sender, normalised.

        It is the copy the Undo embeds, which its sender wrote, so it only
        selects which recorded Offer the Undo names: the sender's standing is
        checked against that Offer, never against this claim (CM-21-015).
        The Undo's own sender when the copy names none.
        """
        embedded = self.activity.object_ if self.activity else None
        actor = (
            embedded.get("actor")
            if isinstance(embedded, dict)
            else getattr(embedded, "actor", None)
        )
        actor_id = _as_id(actor)
        return normalise_actor_id(actor_id) if actor_id else self.actor_id


class InviteActorToCaseReceivedEvent(VultronEvent):
    """Actor invited another actor to join a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.INVITE_ACTOR_TO_CASE] = (
        MessageSemantics.INVITE_ACTOR_TO_CASE
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]

    @property
    def case_id(self) -> str | None:
        """The case the Invite's stub names (CM-11-003), not the stub's ID."""
        return stub_case_id(self.target)


class AcceptInviteActorToCaseReceivedEvent(VultronEvent):
    """Actor accepted an invitation to join a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE] = (
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE
    )

    @property
    def case_id(self) -> str | None:
        """The case the nested Invite's stub names (CM-11-003)."""
        return stub_case_id(self.inner_target)

    @property
    def invite_id(self) -> str | None:
        """The Invite the reply answers; the CASE_MANAGER's record of it, not
        the copy embedded here, governs the reply (CM-11-017)."""
        return self.object_id

    @property
    def invitee_id(self) -> str | None:
        return self.inner_object_id

    @property
    def invitee(self) -> "CoreObject | None":
        return cast("CoreObject | None", self.inner_object)


class RejectInviteActorToCaseReceivedEvent(VultronEvent):
    """Actor rejected an invitation to join a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE] = (
        MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]

    @property
    def invite_id(self) -> str | None:
        return self.object_id

    @property
    def invite(self) -> "VultronActivity | None":
        return cast("VultronActivity | None", self.object_)

    @property
    def case_id(self) -> str | None:
        """The case the nested Invite's stub names (CM-11-003)."""
        return stub_case_id(self.inner_target)


class InviteActorToFullCaseReceivedEvent(VultronEvent):
    """The CASE_MANAGER invited a joined participant to judge the case.

    ``Invite(Actor)[target=VulnerabilityCase]`` — the full-case Invite
    (CM-11-010, VAM-04-011).  The invitee already holds the case from the
    Announce, so the Invite names it by ID; ``ledger_tail`` is the
    CASE_MANAGER's ledger tail when it issued the Invite, the floor the
    invitee's reply must reach.  The extractor parsed it from the Invite's
    ``content`` at the edge (ADR-0032).
    """

    semantic_type: Literal[MessageSemantics.INVITE_ACTOR_TO_FULL_CASE] = (
        MessageSemantics.INVITE_ACTOR_TO_FULL_CASE
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]
    ledger_tail: LedgerPosition

    @property
    def case_id(self) -> str | None:
        return self.target_id

    @property
    def invitee_id(self) -> str | None:
        return self.object_id


class _FullCaseInviteReplyEvent(VultronEvent):
    """Shared shape of the three replies to the full-case Invite (CM-11-011).

    The reply's ``object`` is the Invite, so the case and the invited actor
    are the Invite's ``target`` and ``object``.  ``ledger_tail`` is the
    replier's own ledger position when it decided, parsed from the reply's
    ``content`` at the edge (ADR-0032).
    """

    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]
    ledger_tail: LedgerPosition

    @property
    def invite_id(self) -> str | None:
        return self.object_id

    @property
    def case_id(self) -> str | None:
        return self.inner_target_id

    @property
    def invitee_id(self) -> str | None:
        return self.inner_object_id


class AcceptInviteActorToFullCaseReceivedEvent(_FullCaseInviteReplyEvent):
    """The invitee judged the case valid: ``Accept(full-case Invite)`` (RV)."""

    semantic_type: Literal[
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_FULL_CASE
    ] = MessageSemantics.ACCEPT_INVITE_ACTOR_TO_FULL_CASE


class TentativeRejectInviteActorToFullCaseReceivedEvent(
    _FullCaseInviteReplyEvent
):
    """The invitee judged the case invalid: ``TentativeReject(Invite)`` (RI)."""

    semantic_type: Literal[
        MessageSemantics.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE
    ] = MessageSemantics.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE


class RejectInviteActorToFullCaseReceivedEvent(_FullCaseInviteReplyEvent):
    """The invitee closed the case: ``Reject(full-case Invite)`` (RC)."""

    semantic_type: Literal[
        MessageSemantics.REJECT_INVITE_ACTOR_TO_FULL_CASE
    ] = MessageSemantics.REJECT_INVITE_ACTOR_TO_FULL_CASE


class AnnounceVulnerabilityCaseReceivedEvent(VultronEvent):
    """Case owner announced full VulnerabilityCase details to this actor."""

    semantic_type: Literal[MessageSemantics.ANNOUNCE_VULNERABILITY_CASE] = (
        MessageSemantics.ANNOUNCE_VULNERABILITY_CASE
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]


class OfferCaseParticipantReceivedEvent(VultronEvent):
    """Case Owner received Offer(CaseParticipant) from the CaseActor.

    Sent by the CaseActor to the Case Owner's inbox after transforming
    Offer(Actor, Case) into Offer(CaseParticipant{actor, roles}, Case)
    (CM-16-003, CM-16-004, ADR-0026).
    """

    semantic_type: Literal[MessageSemantics.OFFER_CASE_PARTICIPANT] = (
        MessageSemantics.OFFER_CASE_PARTICIPANT
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]


class AcceptOfferCaseParticipantReceivedEvent(VultronEvent):
    """CaseActor received Accept(Offer(CaseParticipant)) from the Case Owner.

    The Case Owner's decision on a suggested actor (CM-16-006, ADR-0026).
    The CASE_MANAGER's answer to the recommender is
    :class:`AcceptActorRecommendationReceivedEvent`.
    """

    semantic_type: Literal[MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT] = (
        MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]


class RejectOfferCaseParticipantReceivedEvent(VultronEvent):
    """CaseActor received Reject(Offer(CaseParticipant)) from the Case Owner.

    The Case Owner's decision on a suggested actor (CM-16-007, ADR-0026).
    The CASE_MANAGER's answer to the recommender is
    :class:`RejectActorRecommendationReceivedEvent`.
    """

    semantic_type: Literal[MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT] = (
        MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]


class AcceptActorRecommendationReceivedEvent(VultronEvent):
    """A recommender received the CASE_MANAGER's Accept(Offer(Actor, Case)).

    The CASE_MANAGER's answer to a suggestion, sent once the Case Owner has
    accepted it (CM-16-006) or when the suggested actor is already invited or
    joined (CM-16-009).  ``in_reply_to`` is the recommender's Offer.
    """

    semantic_type: Literal[MessageSemantics.ACCEPT_ACTOR_RECOMMENDATION] = (
        MessageSemantics.ACCEPT_ACTOR_RECOMMENDATION
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]


class RejectActorRecommendationReceivedEvent(VultronEvent):
    """A recommender received the CASE_MANAGER's Reject(Offer(Actor, Case)).

    The CASE_MANAGER's answer to a suggestion the Case Owner declined
    (CM-16-007).  ``in_reply_to`` is the recommender's Offer.
    """

    semantic_type: Literal[MessageSemantics.REJECT_ACTOR_RECOMMENDATION] = (
        MessageSemantics.REJECT_ACTOR_RECOMMENDATION
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]
