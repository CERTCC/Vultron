"""Per-semantic inbound domain event types for actor / case-membership activities.

Covers suggest-actor, ownership-transfer, and invite-actor-to-case semantics.
"""

from typing import TYPE_CHECKING, Literal, cast

from vultron.core.models.activity import VultronActivity
from vultron.core.models.events.base import MessageSemantics, VultronEvent

if TYPE_CHECKING:
    from vultron.core.models.base import VultronObject
    from vultron.core.models.case import VulnerabilityCase as VultronCase
else:
    VultronObject = object
    VultronCase = object


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
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.inner_object)


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


class AcceptInviteActorToCaseReceivedEvent(VultronEvent):
    """Actor accepted an invitation to join a VulnerabilityCase."""

    semantic_type: Literal[MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE] = (
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE
    )

    @property
    def case_id(self) -> str | None:
        return self.inner_target_id

    @property
    def case(self) -> "VultronCase | None":
        return cast("VultronCase | None", self.inner_target)

    @property
    def invitee_id(self) -> str | None:
        return self.inner_object_id

    @property
    def invitee(self) -> "VultronObject | None":
        return cast("VultronObject | None", self.inner_object)


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
        return self.inner_target_id


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
