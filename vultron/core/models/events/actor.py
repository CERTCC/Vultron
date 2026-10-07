"""Per-semantic inbound domain event types for actor / case-membership activities.

Covers suggest-actor, ownership-transfer, and invite-actor-to-case semantics.
"""

from typing import TYPE_CHECKING, Literal, cast

from vultron.core.models.activity import VultronActivity
from vultron.core.models.case_stub import stub_case_id
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.ledger_position import LedgerPosition

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
    """Offering actor received Accept(Offer(CaseParticipantRole, ...)).

    The ADR-0039 canonical role-delegation acceptance: the target Actor (or
    their CaseActor representative) accepted the role offer.
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
    """Offering actor received Reject(Offer(CaseParticipantRole, ...)).

    The ADR-0039 canonical role-delegation rejection: the target Actor (or
    their CaseActor representative) declined the role offer.
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


class OfferCaseOwnershipTransferReceivedEvent(VultronEvent):
    """Actor offered ownership of a VulnerabilityCase to another actor."""

    semantic_type: Literal[MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER] = (
        MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]


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

    Supersedes the earlier ACCEPT_ACTOR_RECOMMENDATION semantic with a name
    anchored to the wire activity being accepted (CM-16-006, ADR-0026).
    """

    semantic_type: Literal[MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT] = (
        MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]


class RejectOfferCaseParticipantReceivedEvent(VultronEvent):
    """CaseActor received Reject(Offer(CaseParticipant)) from the Case Owner.

    Supersedes the earlier REJECT_ACTOR_RECOMMENDATION semantic with a name
    anchored to the wire activity being rejected (CM-16-007, ADR-0026).
    """

    semantic_type: Literal[MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT] = (
        MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]
