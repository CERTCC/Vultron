#!/usr/bin/env python

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

"""Domain representation of a case proposal (CP-01-001, ADR-0211).

A ``CaseProposal`` is what a report receiver sends a dedicated CASE_MANAGER
to ask it to create a case around a report (CP-01).  The wire name
``as_CaseProposal`` is an alias of :class:`CaseProposal` (ARCH-25-003): a
``by_alias`` dump is its AS2 form, and core builds no wire object.

``caseInputs`` (:class:`ProposedCaseInputs`) is the starting content the
proposer states for the case (CP-01-022).  It is all or nothing: present, it
speaks for every input and the CASE_MANAGER reads no CSAF document
(CP-01-024); absent, the CASE_MANAGER may read the document on the carried
Offer instead (CP-01-025).  It states no P: whether the disclosure date has
passed is judged when the case is built (CP-01-023).
"""

from collections.abc import Mapping
from typing import ClassVar, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

from vultron.core.models._helpers import timestamp_serializer
from vultron.core.models._helpers.inbound import project_wire_snapshot_to_core
from vultron.core.models.activity import VultronOffer
from vultron.core.models.base import (
    CoreObject,
    NonEmptyString,
    PropertyValueKind,
    ValidatedAssignmentMixin,
    vultron_property,
)
from vultron.core.models.base.core_object import CoreObjectOrIri
from vultron.core.models.case_reference import CaseReferenceLink
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.vulnerability_item import (
    VUL_IDS_PROPERTY,
    VUL_NOTES_PROPERTY,
    VulnerabilityItemId,
    VulnerabilityItemNote,
)
from vultron.core.models.wire_keys import wire_key
from vultron.enums.roles import CVDRole, serialize_roles, validate_roles

#: The one declaration of ``referenceLinks``, shared by the case inputs and
#: each proposed item, so the wire name means one thing (VM-10-012).
_REFERENCE_LINKS_PROPERTY = vultron_property(
    (
        "The external references a case proposer states, each a Link to "
        "the referenced resource"
    ),
    PropertyValueKind.SET,
    items=PropertyValueKind.IRI,
)


class _ProposalValue(ValidatedAssignmentMixin, BaseModel):
    """A value a proposal carries: camelCase on the wire, no unknown key."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )


class ProposedVulnerabilityItem(_ProposalValue):
    """One vulnerability item a proposer states for a new case (CP-01-022).

    The content of a :class:`~vultron.core.models.vulnerability_item.\
VulnerabilityItem` with no id and no time of its own: the CASE_MANAGER
    builds the item, so it mints the id and stamps the time (ADR-0176).  Each
    of ``reference_links`` becomes a case reference held inline on the item.
    """

    ids: list[VulnerabilityItemId] = Field(
        default_factory=list, json_schema_extra=VUL_IDS_PROPERTY
    )
    name: NonEmptyString | None = None
    vul_notes: list[VulnerabilityItemNote] = Field(
        default_factory=list, json_schema_extra=VUL_NOTES_PROPERTY
    )
    reference_links: list[CaseReferenceLink] = Field(
        default_factory=list, json_schema_extra=_REFERENCE_LINKS_PROPERTY
    )


class ProposedCaseInputs(_ProposalValue):
    """The starting content a proposer states for a new case (CP-01-022).

    Present on a proposal, it speaks for every input: an empty
    ``proposed_items`` list or a false ``exploit_public`` is the proposer's
    word, never refilled from a CSAF document (CP-01-024).

    Fields:
        name: The case's name.
        summary: The case's summary.
        exploit_public: Whether an exploit is public (X).
        attacks_observed: Whether attacks are observed (A).
        proposed_items: The case's vulnerability items.
        reference_links: The case's references, each a Link.
        disclosure_date: The earliest CSAF ``vulnerabilities[].disclosure_date``
            as the document states it, unjudged (CP-01-023).  No field states
            P: the CASE_MANAGER judges the date when it builds the case.
    """

    name: NonEmptyString | None = None
    summary: NonEmptyString | None = None
    exploit_public: bool = Field(
        default=False,
        json_schema_extra=vultron_property(
            "Whether a case proposer states that an exploit is public",
            PropertyValueKind.PLAIN,
        ),
    )
    attacks_observed: bool = Field(
        default=False,
        json_schema_extra=vultron_property(
            "Whether a case proposer states that attacks are observed",
            PropertyValueKind.PLAIN,
        ),
    )
    proposed_items: list[ProposedVulnerabilityItem] = Field(
        default_factory=list,
        json_schema_extra=vultron_property(
            (
                "The vulnerability items a case proposer states for a new "
                "case, each with no id of its own"
            ),
            PropertyValueKind.LIST,
        ),
    )
    reference_links: list[CaseReferenceLink] = Field(
        default_factory=list, json_schema_extra=_REFERENCE_LINKS_PROPERTY
    )
    disclosure_date: AwareDatetime | None = Field(
        default=None,
        json_schema_extra=vultron_property(
            (
                "The earliest disclosure date a case proposer's CSAF document "
                "states, as the document states it"
            ),
            PropertyValueKind.PLAIN,
        ),
    )

    _serialize_disclosure_date = timestamp_serializer("disclosure_date")


class CaseProposal(CoreObject):
    """A report receiver's request that a CASE_MANAGER create a case (CP-01-001).

    Declares ``object_`` and ``in_reply_to`` in :attr:`inline_required_refs`,
    so persistence keeps the report and the Offer inline rather than
    collapsing them to their ids (CP-01-004, CP-01-008; #2482).

    The CASE_MANAGER evaluates the proposal and answers with either
    ``Accept(CaseProposal)`` followed by ``Create(VulnerabilityCase)``
    (CP-05-003) or ``Reject(CaseProposal)`` (CP-05-004).

    Fields:
        attributed_to: The report receiver that originated the proposal
            (CP-01-003).
        object_: The inline ``VulnerabilityReport`` the case is to be created
            around (CP-01-004, AKM-03-003); a bare id is what a stored row
            may collapse it to.
        target: The CASE_MANAGER service the proposal is addressed to
            (CP-01-005).
        summary: Optional human-readable description (CP-01-006).
        in_reply_to: The ``Offer(VulnerabilityReport)`` this proposal
            descends from (CP-01-007): inline when the proposer holds it
            (CP-01-008), else its id.  The inline Offer is how the
            Reporter's proposed embargo terms (EP-04-004) reach case
            creation.  Held as the parse edge built it, or as a
            :class:`VultronOffer` when read from a dump.
        proposer_case_roles: The CVD roles the proposer holds in a case it
            owns (CP-01-011, CP-01-013, ADR-0133); never ``CASE_MANAGER``
            (CP-01-012).
        case_inputs: The starting content the proposer states for the case
            (CP-01-022); ``None`` when it states none.
    """

    # CP-01-004 / AKM-03-003: the report is carried, not referenced; the Offer
    # too, when the proposer holds it (CP-01-008).
    inline_required_refs: ClassVar[frozenset[str]] = frozenset(
        {"object_", "in_reply_to"}
    )

    type_: Literal["CaseProposal"] = Field(
        default="CaseProposal",
        validation_alias="type",
        serialization_alias="type",
    )
    attributed_to: NonEmptyString = Field(  # pyright: ignore[reportIncompatibleVariableOverride]
        ...,
        description="URI of the report receiver that originated the proposal.",
    )
    object_: VulnerabilityReport | NonEmptyString = Field(
        ...,
        validation_alias="object",
        serialization_alias="object",
        description="Inline VulnerabilityReport; URI-only refs not permitted (AKM-03-003).",
    )
    target: NonEmptyString = Field(
        ...,
        description="URI of the prospective case-actor service.",
    )
    in_reply_to: CoreObjectOrIri | None = Field(  # pyright: ignore[reportIncompatibleVariableOverride]
        default=None,
        description=(
            "The Offer(VulnerabilityReport) this proposal answers, inline"
            " (CP-01-008) or by id (CP-01-007)."
        ),
    )
    proposer_case_roles: list[CVDRole] = Field(
        default_factory=list,
        description=(
            "CVD roles the proposer holds in a case it owns, from its own"
            " default_case_roles (CP-01-011, CP-01-013)."
        ),
        json_schema_extra=vultron_property(
            "The CVD roles a case proposer holds in a case it owns",
            PropertyValueKind.SET,
        ),
    )
    case_inputs: ProposedCaseInputs | None = Field(
        default=None,
        json_schema_extra=vultron_property(
            (
                "The starting content a case proposer states for the case it "
                "proposes; present, it speaks for every input"
            ),
            PropertyValueKind.PLAIN,
        ),
    )

    @field_serializer("proposer_case_roles")
    def _serialize_proposer_case_roles(
        self, value: list[CVDRole]
    ) -> list[str]:
        return serialize_roles(value)

    @field_validator("proposer_case_roles", mode="before")
    @classmethod
    def _validate_proposer_case_roles(cls, value: object) -> list[CVDRole]:
        return validate_roles(
            value, field_name=wire_key("proposer_case_roles")
        )

    @field_validator("proposer_case_roles")
    @classmethod
    def _proposer_claims_no_case_manager(
        cls, value: list[CVDRole]
    ) -> list[CVDRole]:
        """Refuse a claim to ``CASE_MANAGER`` (CP-01-012).

        Only the CaseActor holds that role; a proposer that could name it here
        would seat itself as the case's manager.
        """
        if CVDRole.CASE_MANAGER in value:
            raise ValueError(
                f"CaseProposal {wire_key('proposer_case_roles')} claims"
                " CASE_MANAGER, which only the CaseActor holds (CP-01-012)"
            )
        return value

    @field_validator("in_reply_to", mode="before")
    @classmethod
    def _read_offer_dump(cls, value: object, info: ValidationInfo) -> object:
        """Read a dumped Offer back as a :class:`VultronOffer`.

        The parse edge hands the Offer over already built; a stored row or a
        received dict holds it as a mapping, which no other slot branch
        takes.
        """
        if isinstance(value, Mapping):
            return VultronOffer.model_validate(
                project_wire_snapshot_to_core(VultronOffer, value),
                context=info.context,
            )
        return value

    @field_validator("in_reply_to")
    @classmethod
    def _in_reply_to_is_an_offer(cls, value: object) -> object:
        """Refuse an embedded object that is not an Offer (CP-01-007)."""
        if value is None or isinstance(value, str):
            return value
        kind = getattr(value, "type_", None)
        if str(kind) != "Offer":
            raise ValueError(
                "CaseProposal inReplyTo must be the Offer(VulnerabilityReport)"
                f" it answers or its id, got a {kind!r} (CP-01-007)"
            )
        return value

    @model_validator(mode="after")
    def _inline_offer_submitted_this_report(self) -> Self:
        """An inline Offer in ``inReplyTo`` is the one that brought the report.

        Raises ``ValueError`` (a Pydantic validation error) when the inline
        Offer submitted a different report: one proposal cannot answer
        another report's submission, and the case-actor would read another
        report's proposed terms (EP-04-009).  A bare Offer id carries
        nothing to compare.
        """
        offer = self.in_reply_to
        if offer is None or isinstance(offer, str):
            return self
        offered = getattr(offer, "object_", None)
        offered_report = getattr(offered, "id_", offered)
        proposed_report = getattr(self.object_, "id_", self.object_)
        if (
            offered_report is not None
            and proposed_report is not None
            and offered_report != proposed_report
        ):
            raise ValueError(
                f"CaseProposal object {proposed_report!r} is not the report"
                f" the inline Offer submitted ({offered_report!r}) (CP-01-008)"
            )
        return self


__all__ = [
    "CaseProposal",
    "ProposedCaseInputs",
    "ProposedVulnerabilityItem",
]
