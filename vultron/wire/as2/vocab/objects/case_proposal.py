"""Wire-layer vocabulary type for the CaseProposal protocol.

Provides :class:`as_CaseProposal`, the AS2 Object type used in the
``Create(as_CaseProposal)`` / ``Accept(as_CaseProposal)`` /
``Reject(as_CaseProposal)`` message flow defined in ADR-0023.

Spec: ``specs/case-proposal.yaml`` CP-01-001 through CP-01-006.
"""

# pyright: reportGeneralTypeIssues=false
# Rationale: as_CaseProposal narrows several optional base-class fields to
# required.  The formatter wraps the Field() calls across multiple lines,
# making inline pyright-ignore comments unreliable (see
# notes/codebase-structure-fastapi-patterns.md
# § "The Formatter Can Invalidate Inline Type-Checker Suppressions").

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from typing import ClassVar, TypeAlias

from pydantic import Field, model_validator

from vultron.enums.object_types import VultronObjectType as VO_type
from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.base import ActivityStreamRequiredRef
from vultron.wire.as2.vocab.objects.base import as_VultronObject
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)


class as_CaseProposal(as_VultronObject):
    """Wire representation of a CaseProposal object (CP-01-001).

    Declares ``object_`` in :attr:`inline_required_refs`, so persistence keeps
    the report inline rather than collapsing it to its id (CP-01-004; #2482).

    A report receiver creates this object to request that a dedicated
    case-actor service initialise a new :class:`VulnerabilityCase`.
    The case-actor evaluates the proposal and responds with either
    ``Accept(as_CaseProposal)`` followed by
    ``Create(VulnerabilityCase)`` (happy path, CP-05-003) or
    ``Reject(as_CaseProposal)`` (rejection path, CP-05-004).

    All classes in ``vultron/wire/as2/vocab/objects/`` use the ``as_``
    prefix (ARCH-14-001); the bare name ``CaseProposal`` is reserved for
    any future core domain model.

    Fields:
        type_: Always ``"CaseProposal"``; registered in ``VultronObjectType``.
        attributed_to: Required URI of the report receiver that originated
            the proposal (CP-01-003).
        object_: Required inline ``as_VulnerabilityReport`` around which the
            case is to be created.  URI-only references are not permitted
            (CP-01-004, AKM-03-001).
        target: Required URI of the prospective case-actor service to
            which the proposal is addressed (CP-01-005).
        summary: Optional human-readable description of the proposal
            (CP-01-006).
        offer_id: Optional URI of the ``Offer(VulnerabilityReport)`` this
            proposal descends from, with ``offer_actor_id`` naming its sender
            (CP-01-007).
        in_reply_to: The ``Offer(VulnerabilityReport)`` itself, inline, when
            the proposer holds it (CP-01-008).  The proposal answers the
            Reporter's submission, which is what AS2's ``inReplyTo`` says; and
            a sender inlines the objects it introduces (ADR-0107), the
            case-actor having never seen the Offer.  It is how the Reporter's
            proposed embargo terms (EP-04-004) reach case creation.
    """

    # CP-01-004 / AKM-03-001: the report is carried, not referenced. Declared
    # here so persistence keeps it inline; see as_VultronObject's docstring.
    inline_required_refs: ClassVar[frozenset[str]] = frozenset(
        {"object_", "in_reply_to"}
    )

    type_: VO_type = Field(
        default=VO_type.CASE_PROPOSAL,
        validation_alias="type",
        serialization_alias="type",
    )

    # CP-01-003: report receiver URI that originated the proposal.
    attributed_to: NonEmptyString = Field(
        ...,
        description="URI of the report receiver that originated the proposal.",
    )

    # CP-01-004: fully inline as_VulnerabilityReport; URI references not permitted
    # at the wire boundary.  ``ActivityStreamRequiredRef`` still admits ``str`` in
    # its union, so the annotation alone does not carry CP-01-004 —
    # ``inline_required_refs`` below is what makes it hold through storage.
    #
    # This comment used to claim the DataLayer could "store/restore the
    # dehydrated string ID; _rehydrate_fields expands it back".  It cannot, and
    # that premise was #2482: ingress stores only the first level of nesting, so
    # the report never got a record of its own and there was nothing for the
    # re-read to expand.  The id came back bare and every consequence of the
    # report degraded to a silent best-effort skip.
    object_: ActivityStreamRequiredRef[as_VulnerabilityReport] = Field(
        ...,
        validation_alias="object",
        serialization_alias="object",
        description="Inline as_VulnerabilityReport; URI-only refs not permitted (AKM-03-001).",
    )

    # CP-01-005: URI of the prospective case-actor service.
    target: NonEmptyString = Field(
        ...,
        description="URI of the prospective case-actor service.",
    )

    # CP-01-006: optional human-readable summary.
    # summary is inherited as Any|None from as_Object; narrowed here.
    summary: NonEmptyString | None = Field(
        default=None,
        description="Optional human-readable description of the proposal.",
    )

    # CP-01-007: provenance of the report this proposal is about.
    #
    # The CaseActor commits the canonical `add_report_to_case` ledger entry, and
    # invited actors rebuild their `VultronOfferRecord` from that entry's
    # snapshot (ADR-0035 DL-06-002, SYNC-02-002). The CaseActor cannot look the
    # offer up: the `OfferRecord` lives in the store of the actor that received
    # the Offer, and a co-located CaseActor has its own store and no read into a
    # sibling's (ADR-0073, PCR-01-003). So the offer travels here, on the
    # proposal, for the same reason and by the same rule as the report itself
    # (CP-01-004).
    #
    # Without it the snapshot carried no `offerId`, every invited actor's
    # `ApplyOfferReportFromLedgerNode` logged "no offerId — skipping
    # (non-fatal)", and `validate-report` answered `404 Offer not found` to an
    # invitee that had done everything right (#2548).
    offer_id: NonEmptyString | None = Field(
        default=None,
        validation_alias="offerId",
        serialization_alias="offerId",
        description="URI of the Offer(VulnerabilityReport) this proposal descends from.",
    )
    offer_actor_id: NonEmptyString | None = Field(
        default=None,
        validation_alias="offerActorId",
        serialization_alias="offerActorId",
        description="URI of the actor that sent the Offer named by offer_id.",
    )
    # CP-01-008: the Offer itself, carried whole.  ``offer_id``/``offer_actor_id``
    # are its bare-reference twin; when both forms are present they MUST agree.
    # Typed on the base ``as_Offer``: the parser expands an inline Offer to the
    # class the wire registry holds for ``type: Offer``, which is the base.
    in_reply_to: as_Offer | None = Field(  # pyright: ignore[reportIncompatibleVariableOverride]
        default=None,
        validation_alias="inReplyTo",
        serialization_alias="inReplyTo",
        description=(
            "The Offer(VulnerabilityReport) this proposal answers, inline"
            " (CP-01-008)."
        ),
    )

    @model_validator(mode="after")
    def _offer_reference_agrees_with_inline_offer(self) -> "as_CaseProposal":
        """The bare provenance and the inline Offer name the same submission.

        Raises ``ValueError`` (a Pydantic validation error) when both forms are
        present and disagree: one proposal cannot descend from two Offers.
        """
        offer = self.in_reply_to
        if offer is None:
            return self
        if self.offer_id is not None and offer.id_ != self.offer_id:
            raise ValueError(
                f"as_CaseProposal offerId {self.offer_id!r} does not name the"
                f" inline Offer {offer.id_!r} carried in inReplyTo (CP-01-008)"
            )
        offer_actor = getattr(offer.actor, "id_", offer.actor)
        if (
            self.offer_actor_id is not None
            and offer_actor is not None
            and offer_actor != self.offer_actor_id
        ):
            raise ValueError(
                f"as_CaseProposal offerActorId {self.offer_actor_id!r} does"
                f" not name the inline Offer's actor {offer_actor!r}"
                " (CP-01-008)"
            )
        # The Offer must be the one that brought *this* report: otherwise the
        # case-actor would read another report's proposed terms (EP-04-009).
        offered_report = getattr(offer.object_, "id_", offer.object_)
        proposed_report = getattr(self.object_, "id_", self.object_)
        if (
            offered_report is not None
            and proposed_report is not None
            and offered_report != proposed_report
        ):
            raise ValueError(
                f"as_CaseProposal object {proposed_report!r} is not the report"
                f" the inline Offer submitted ({offered_report!r}) (CP-01-008)"
            )
        return self


as_CaseProposalRef: TypeAlias = ActivityStreamRef[as_CaseProposal]
