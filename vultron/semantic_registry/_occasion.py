"""Occasions: the situations a sender conveys with one registry entry.

An **occasion** is a situation in a case that a sender conveys by sending a
particular wire activity, sometimes narrowed by a distinguishing field value,
state context or sender standing (glossary, ADR-0128).  One ``SemanticEntry``
carries one or more occasions: three situations — vendor awareness, fix ready,
fix deployed — share ``Add(ParticipantStatus)``, told apart by its ``vf`` and
``d`` dimensions.

This module holds the value objects only.  An occasion records what only a
human can supply; everything derivable from it (the mapping status, the
"Sent by" and "Send to" wording) is derived by ``vultron.metadata.msm``
(MSM-08-005, MSM-08-006, MSM-08-009).

Spec: MSM-08-001, MSM-08-002, MSM-08-005, MSM-08-007, MSM-08-009,
MSM-08-011.
"""

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

import functools
import operator
import types
import typing
from enum import Enum, StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vultron.core.behaviors.sender_entitlement import (
    AddresseeSide,
    SenderEntitlementKind,
)
from vultron.core.models.dimensions import (
    DIMENSION_STATE_FIELD,
    is_dimension_model,
)
from vultron.core.models.wire_keys import wire_key
from vultron.enums.roles import CVDRole
from vultron.primitives import NonEmptyString


class MessagePage(StrEnum):
    """The ``docs/reference/messages/`` page that owns an entry (MSM-06-002).

    Values are the page file stems; member order is the canonical display
    order of the pages.
    """

    RM = "rm"
    EM = "em"
    CS = "cs"
    GENERAL = "general"
    FAULTS_AND_ACKNOWLEDGEMENTS = "faults_and_acknowledgements"
    CASE_MANAGEMENT = "case_management"
    CASE_PROPOSAL = "case_proposal"
    LEDGER_REPLICATION = "ledger_replication"


class HowToGuide(StrEnum):
    """The how-to guides an occasion declares, as ``docs/``-relative paths."""

    REPORT_VULNERABILITY = (
        "howto/activitypub/activities/report_vulnerability.md"
    )
    MANAGE_CASE = "howto/activitypub/activities/manage_case.md"
    INITIALIZE_CASE = "howto/activitypub/activities/initialize_case.md"
    INVITE_ACTOR = "howto/activitypub/activities/invite_actor.md"
    MANAGE_PARTICIPANTS = "howto/activitypub/activities/manage_participants.md"
    ROLE_DELEGATION = "howto/activitypub/activities/role_delegation.md"
    ESTABLISH_EMBARGO = "howto/activitypub/activities/establish_embargo.md"
    MANAGE_EMBARGO = "howto/activitypub/activities/manage_embargo.md"
    STATUS_UPDATES = "howto/activitypub/activities/status_updates.md"
    SUGGEST_ACTOR = "howto/activitypub/activities/suggest_actor.md"


class ProtocolShorthand(StrEnum):
    """The formal protocol message set (``formal_protocol/messages.md``).

    Unlike the legacy simulator's ``MessageTypes``, this lists the revision
    messages ``EV``, ``EJ`` and ``EC`` in their own right, because the wire
    vocabulary collapses them onto ``EP``, ``ER`` and ``EA`` (MSM-02).
    """

    RS = "RS"
    RI = "RI"
    RV = "RV"
    RD = "RD"
    RA = "RA"
    RC = "RC"
    RK = "RK"
    RE = "RE"
    EP = "EP"
    ER = "ER"
    EA = "EA"
    EV = "EV"
    EJ = "EJ"
    EC = "EC"
    ET = "ET"
    EK = "EK"
    EE = "EE"
    CV = "CV"
    CF = "CF"
    CD = "CD"
    CP = "CP"
    CX = "CX"
    CA = "CA"
    CK = "CK"
    CE = "CE"
    GI = "GI"
    GK = "GK"
    GE = "GE"

    @property
    def formal_name(self) -> str:
        """The message's name in ``formal_protocol/messages.md``, e.g.
        ``"Fix Readiness"`` for ``CF`` (MSM-08-008)."""
        return _FORMAL_NAMES[self]

    @property
    def formal_section(self) -> str:
        """The anchor of the ``formal_protocol/messages.md`` section that
        defines this message's family, e.g. ``"cs-message-types"``."""
        return _FORMAL_SECTIONS[self.value[0]]


#: The section of ``formal_protocol/messages.md`` defining each family of
#: shorthands, keyed by the shorthand's first letter (its state machine).
_FORMAL_SECTIONS: dict[str, str] = {
    "R": "rm-message-types",
    "E": "em-message-types",
    "C": "cs-message-types",
    "G": "other-message-types",
}

#: The formal message names, as ``docs/reference/formal_protocol/messages.md``
#: gives them; ``test_semantic_registry_occasions.py`` holds the two in step.
_FORMAL_NAMES: dict[ProtocolShorthand, str] = {
    ProtocolShorthand.RS: "Report Submission",
    ProtocolShorthand.RI: "Report Invalid",
    ProtocolShorthand.RV: "Report Valid",
    ProtocolShorthand.RD: "Report/Case Deferred",
    ProtocolShorthand.RA: "Report/Case Accepted",
    ProtocolShorthand.RC: "Report Closed",
    ProtocolShorthand.RK: "Report Acknowledgment",
    ProtocolShorthand.RE: "Report Error",
    ProtocolShorthand.EP: "Embargo Proposal",
    ProtocolShorthand.ER: "Embargo Proposal Rejection",
    ProtocolShorthand.EA: "Embargo Proposal Acceptance",
    ProtocolShorthand.EV: "Embargo Revision Proposal",
    ProtocolShorthand.EJ: "Embargo Revision Rejection",
    ProtocolShorthand.EC: "Embargo Revision Acceptance",
    ProtocolShorthand.ET: "Embargo Termination",
    ProtocolShorthand.EK: "Embargo Acknowledgment",
    ProtocolShorthand.EE: "Embargo Error",
    ProtocolShorthand.CV: "Vendor Awareness",
    ProtocolShorthand.CF: "Fix Readiness",
    ProtocolShorthand.CD: "Fix Deployed",
    ProtocolShorthand.CP: "Public Awareness",
    ProtocolShorthand.CX: "Exploit Public",
    ProtocolShorthand.CA: "Attacks Observed",
    ProtocolShorthand.CK: "CS Acknowledgment",
    ProtocolShorthand.CE: "CS Error",
    ProtocolShorthand.GI: "General Inquiry",
    ProtocolShorthand.GK: "General Acknowledgment",
    ProtocolShorthand.GE: "General Error",
}


#: An occasion anchor: lowercase words joined by hyphens.
ANCHOR_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_EXAMPLE_NAME_PATTERN = r"^[a-z_][a-z0-9_]*$"


def _enum_classes(annotation: object) -> list[type[Enum]]:
    """Return the ``Enum`` classes named by *annotation*, unwrapping unions."""
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return [annotation]
    origin = typing.get_origin(annotation)
    if origin is typing.Union or origin is types.UnionType:
        found: list[type[Enum]] = []
        for arg in typing.get_args(annotation):
            found.extend(_enum_classes(arg))
        return found
    return []


def _state_annotation(annotation: object) -> object:
    """Resolve a dimension annotation to its ``state`` annotation.

    A status dimension travels as its bare state value (ARCH-25-005,
    ADR-0099), so ``PxaDimension`` resolves to ``CS_pxa``.  An optional
    dimension (``VfDimension | None``, absent for a participant whose role
    does not carry it, ADR-0075) resolves member by member.  Any other
    annotation is returned unchanged.
    """
    if is_dimension_model(annotation):
        dimension = typing.cast(type[BaseModel], annotation)
        return dimension.model_fields[DIMENSION_STATE_FIELD].annotation
    origin = typing.get_origin(annotation)
    if origin is typing.Union or origin is types.UnionType:
        members = [
            _state_annotation(arg) for arg in typing.get_args(annotation)
        ]
        return functools.reduce(operator.or_, members)
    return annotation


def _field_annotation(object_type: type, field_name: str) -> object:
    """Return the annotation of *field_name* on *object_type*, or raise.

    *field_name* is a declared Pydantic field.  A status dimension field
    (``CaseStatus.pxa``, ``ParticipantStatus.vf``) resolves to the
    annotation of the dimension's ``state`` (:func:`_state_annotation`).
    """
    model_fields = getattr(object_type, "model_fields", {})
    if field_name in model_fields:
        return _state_annotation(model_fields[field_name].annotation)
    raise ValueError(
        f"{object_type.__name__} has no typed field {field_name!r}"
    )


def wire_spelling(
    object_type: type[BaseModel], field_name: str, within: str | None = None
) -> str:
    """Return how *field_name* on *object_type* is spelled on the wire.

    A declared field travels under its own AS2 spelling (``CaseStatus.pxa``
    as ``pxaState``, ``ParticipantStatus.vf`` as ``vfState``), the rule
    :func:`~vultron.core.models.wire_keys.wire_key` applies.  A field read
    *within* an embedded model is spelled as a dotted path from
    *object_type*: ``ParticipantStatus.case_status.pxa`` as
    ``caseStatus.pxaState``.
    """
    if within is None:
        return wire_key(field_name, object_type)
    embedded = _embedded_model(object_type, within)
    return f"{wire_key(within, object_type)}.{wire_key(field_name, embedded)}"


def _embedded_model(object_type: type, field_name: str) -> type[BaseModel]:
    """Return the model class *field_name* on *object_type* embeds, or raise.

    *field_name* is a declared Pydantic field typed by one model class,
    optionally ``| None`` (``ParticipantStatus.case_status`` embeds
    ``CaseStatus``).  A dimension field is a state, not an embedded model.
    """
    model_fields = getattr(object_type, "model_fields", {})
    if field_name not in model_fields:
        raise ValueError(
            f"{object_type.__name__} has no typed field {field_name!r}"
        )
    annotation = model_fields[field_name].annotation
    members = (
        typing.get_args(annotation)
        if typing.get_origin(annotation) in (typing.Union, types.UnionType)
        else (annotation,)
    )
    # Only ``| None`` may accompany the model: any other member (an IRI
    # string, say) is a value read() could not look a field up on.
    held = [m for m in members if m is not types.NoneType]
    if not (
        len(held) == 1
        and isinstance(held[0], type)
        and issubclass(held[0], BaseModel)
        and not is_dimension_model(held[0])
    ):
        raise ValueError(
            f"{object_type.__name__}.{field_name} does not embed exactly one"
            " model, so no field can be read within it (MSM-08-002)"
        )
    return held[0]


_FROZEN = ConfigDict(frozen=True, strict=True, arbitrary_types_allowed=True)


class FieldValue(BaseModel):
    """A distinguisher read from the payload: one field holding one value.

    Construction fails unless *value* is a member of the enum that
    *field* is declared with on *object_type*, or on the model that
    *object_type* embeds in its *within* field (MSM-08-002).

    Attributes:
        object_type: The class of the activity's ``object`` that carries the
            field, e.g. ``ParticipantStatus``.
        field: The field name, e.g. ``"vf"``.
        value: The enum member the occasion's payload carries.
        within: The field of *object_type* that embeds the model declaring
            *field*, when the field is not *object_type*'s own: a
            participant's view of the public state is
            ``ParticipantStatus.case_status.pxa``, so ``within`` is
            ``"case_status"`` and ``field`` is ``"pxa"``.
    """

    model_config = _FROZEN

    object_type: type
    field: NonEmptyString
    value: Enum
    within: NonEmptyString | None = None

    @property
    def declaring_type(self) -> type:
        """The class that declares :attr:`field`: *object_type* itself, or
        the model it embeds in :attr:`within`."""
        if self.within is None:
            return self.object_type
        return _embedded_model(self.object_type, self.within)

    @property
    def path(self) -> str:
        """The field's dotted name from *object_type*, e.g.
        ``"case_status.pxa"``, for error messages."""
        if self.within is None:
            return self.field
        return f"{self.within}.{self.field}"

    @model_validator(mode="after")
    def _value_is_a_member_of_the_field_enum(self) -> "FieldValue":
        enums = _enum_classes(
            _field_annotation(self.declaring_type, self.field)
        )
        if not enums:
            raise ValueError(
                f"{self.object_type.__name__}.{self.path} is not typed by an"
                " enum, so it cannot distinguish an occasion (MSM-08-002)"
            )
        if not any(isinstance(self.value, enum) for enum in enums):
            names = ", ".join(enum.__name__ for enum in enums)
            raise ValueError(
                f"{self.value!r} is not a member of {names}, the enum of"
                f" {self.object_type.__name__}.{self.path} (MSM-08-002)"
            )
        return self

    def overlaps(self, other: "Distinguisher") -> bool:
        """Return whether *other* reads this field and holds this value, so
        one activity could match both (MSM-08-011).  A distinguisher on
        another field is not compared."""
        return (
            isinstance(other, FieldValue)
            and (other.object_type, other.within, other.field)
            == (self.object_type, self.within, self.field)
            and other.value == self.value
        )

    def read(self, carrier: object) -> object:
        """Return the value *carrier* holds in this distinguisher's field.

        A status dimension field is read as its ``state``, the value it
        travels as (ARCH-25-005, ADR-0099), so it compares to
        :attr:`value`.  A field *within* an embedded model is read from
        that model; a carrier that embeds none holds no value (``None``).
        """
        if self.within is not None:
            carrier = getattr(carrier, self.within)
            if carrier is None:
                return None
        held = getattr(carrier, self.field)
        if is_dimension_model(type(held)):
            return getattr(held, DIMENSION_STATE_FIELD)
        return held


class StateContext(BaseModel):
    """A distinguisher the payload does not carry: a state of a machine.

    The state is held outside the activity: the case's EM state, or, for
    ``EmbargoRegisterStatus``, the CASE_MANAGER's register status of the
    embargo the activity names, which belongs to that embargo, not to the
    case, and to the CASE_MANAGER's register, not the receiver's.
    Construction fails unless every state is a member of *machine*
    (MSM-08-002).  No example can carry a state context (MSM-08-003).

    Attributes:
        machine: The state machine's state enum, e.g. ``EM``.
        states: The states in which the occasion applies.
    """

    model_config = _FROZEN

    machine: type[Enum]
    states: tuple[Enum, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _states_belong_to_the_machine(self) -> "StateContext":
        foreign = [s for s in self.states if not isinstance(s, self.machine)]
        if foreign:
            raise ValueError(
                f"{foreign!r} are not members of {self.machine.__name__}"
                " (MSM-08-002)"
            )
        return self

    def overlaps(self, other: "Distinguisher") -> bool:
        """Return whether *other* is a context on this machine that shares a
        state, so one activity could match both (MSM-08-011).  A context on
        another machine is not compared."""
        return (
            isinstance(other, StateContext)
            and other.machine is self.machine
            and not set(other.states).isdisjoint(self.states)
        )


class SenderStanding(BaseModel):
    """A distinguisher the payload does not carry: the sender's standing.

    Two occasions can share a wire form and an addressee and differ only in
    who sends them: the Case Owner's request to invite an actor and a
    participant's suggestion are one ``Offer(Actor)``.  The standing is typed
    by the entitlement kinds a receiver checks (HP-01-009), so its wording
    comes from the kind (MSM-08-010).  Construction fails unless *kind* is a
    ``SenderEntitlementKind`` member that requires a standing (MSM-08-002).
    Like a state context, no example can carry it (MSM-08-003).

    Attributes:
        kind: The entitlement kind, e.g. ``SenderEntitlementKind.CASE_OWNER``.
        holds: Whether the occasion's sender holds *kind*.
    """

    model_config = _FROZEN

    kind: SenderEntitlementKind
    holds: bool

    @model_validator(mode="after")
    def _kind_requires_a_standing(self) -> "SenderStanding":
        if self.kind is SenderEntitlementKind.ANY_ACTOR:
            raise ValueError(
                "ANY_ACTOR requires no standing, so it cannot tell two"
                " senders apart (MSM-08-002)"
            )
        return self

    def overlaps(self, other: "Distinguisher") -> bool:
        """Return whether *other* is a standing of this kind that the sender
        holds or lacks alike, so one activity could match both (MSM-08-011).
        A standing of another kind is not compared."""
        return (
            isinstance(other, SenderStanding)
            and other.kind is self.kind
            and other.holds == self.holds
        )


Distinguisher = FieldValue | StateContext | SenderStanding


class Occasion(BaseModel):
    """One situation a sender conveys with an entry's wire activity.

    Holds what only a human can supply (ADR-0128).  The prose fields render
    on reference pages and in how-to guides, so they follow the docs style
    guide and address no reader (MSM-08-007).  The model is strict, so a
    usual sender must be a ``CVDRole`` member, not a string (MSM-08-005).

    Attributes:
        when: The sender's situation, worded to complete "When…", e.g.
            "a Vendor has a fix ready".
        anchor: Stable section anchor, lowercase words joined by hyphens.
        addressee: Whom the activity is sent to, as a side of a sender rule:
            the CASE_MANAGER, a participant, or an actor outside any case.
            It picks the side of the use case's declared rule that gives
            "Sent by", and renders as "Send to"; ``SemanticEntry`` refuses an
            addressee its use case's rule states no side for (MSM-08-009).
        heading: The plain-English heading of the occasion's section, in
            sentence case, e.g. "Add note to case".  Required when the
            occasion has no shorthand.  An occasion whose shorthand is
            carried by another entry too (an expansion such as ``GI``) needs
            one as well, and one whose shorthand is its own must not declare
            one, because its section is headed by the formal name
            (MSM-08-008); both depend on the whole registry, so
            ``vultron.metadata.msm`` checks them, not this model.
        description: One or two sentences on what the activity does.
        example: Name of the ``vocab_examples`` function that builds this
            occasion's example (MSM-08-003).
        distinguisher: What tells this occasion apart from the entry's other
            occasions, when it has any.  It is required when another
            occasion of the entry has the same addressee, which
            ``SemanticEntry`` checks (MSM-08-011).
        howto: The how-to guide whose steps send it.  The guide must embed
            the occasion where a step sends it, or ``msm-occasions`` fails;
            the section's "Seen in" lists that guide and every other page
            that embeds the occasion (#4432).
        shorthand: The formal protocol message it carries, if any.
        usual_senders: The CVD roles that usually send it, beside the rule a
            receiver applies (MSM-08-005).
        notes: Further prose for the occasion's section.
        evolved: ``True`` when the activity serves a formal message's purpose
            on a different axis (MSM-05).  Such an occasion has no shorthand
            to count, which is what leaves ``evolved`` the one declared
            mapping status (MSM-08-006).
    """

    model_config = _FROZEN

    when: NonEmptyString
    anchor: Annotated[str, Field(pattern=ANCHOR_PATTERN)]
    addressee: AddresseeSide
    description: NonEmptyString
    heading: NonEmptyString | None = None
    example: Annotated[str, Field(pattern=_EXAMPLE_NAME_PATTERN)]
    distinguisher: Distinguisher | None = None
    howto: HowToGuide | None = None
    shorthand: ProtocolShorthand | None = None
    usual_senders: tuple[CVDRole, ...] = ()
    notes: NonEmptyString | None = None
    evolved: bool = False

    @model_validator(mode="after")
    def _evolved_has_no_shorthand(self) -> "Occasion":
        if self.evolved and self.shorthand is not None:
            raise ValueError(
                "an evolved occasion has no shorthand of its own (MSM-08-006)"
            )
        return self

    @model_validator(mode="after")
    def _no_shorthand_needs_a_heading(self) -> "Occasion":
        if self.shorthand is None and self.heading is None:
            raise ValueError(
                f"occasion {self.anchor!r} has no shorthand, so its section"
                " needs a plain-English heading (MSM-08-008)"
            )
        return self


__all__ = [
    "ANCHOR_PATTERN",
    "Distinguisher",
    "FieldValue",
    "HowToGuide",
    "MessagePage",
    "Occasion",
    "ProtocolShorthand",
    "SenderStanding",
    "StateContext",
    "wire_spelling",
]
