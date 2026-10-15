"""Occasions: the situations a sender conveys with one registry entry.

An **occasion** is a situation in a case that a sender conveys by sending a
particular wire activity, sometimes narrowed by a distinguishing field value or
state context (glossary, ADR-0128).  One ``SemanticEntry`` carries one or more
occasions: three situations — vendor awareness, fix ready, fix deployed — share
``Add(ParticipantStatus)``, told apart by ``vf_state`` and ``d_state``.

This module holds the value objects only.  An occasion records what only a
human can supply; everything derivable from it (the mapping status, the
"Sent by" wording) is derived by ``vultron.metadata.msm`` (MSM-08-005,
MSM-08-006).

Spec: MSM-08-001, MSM-08-002, MSM-08-005, MSM-08-007.
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

import types
import typing
from enum import Enum, StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


def _field_annotation(object_type: type, field_name: str) -> object:
    """Return the annotation of *field_name* on *object_type*, or raise.

    A field may be a declared Pydantic field or a read property.  A status
    dimension field (``CaseStatus.pxa``) is typed by its dimension object,
    which travels as its bare state value (ARCH-25-005, ADR-0099), so it
    resolves to the annotation of the dimension's ``state``.
    """
    attribute = getattr(object_type, field_name, None)
    if isinstance(attribute, property) and attribute.fget is not None:
        hints = typing.get_type_hints(attribute.fget)
        if "return" in hints:
            return hints["return"]
    model_fields = getattr(object_type, "model_fields", {})
    if field_name in model_fields:
        annotation = model_fields[field_name].annotation
        if is_dimension_model(annotation):
            return annotation.model_fields[DIMENSION_STATE_FIELD].annotation
        return annotation
    raise ValueError(
        f"{object_type.__name__} has no typed field {field_name!r}"
    )


def wire_spelling(object_type: type[BaseModel], field_name: str) -> str:
    """Return how *field_name* on *object_type* is spelled on the wire.

    A declared field travels under its own AS2 spelling (``CaseStatus.pxa``
    as ``pxaState``); a read property under its name camel-cased
    (``ParticipantStatus.vf_state`` as ``vfState``), the same rule
    :func:`~vultron.core.models.wire_keys.wire_key` applies.
    """
    declared = field_name in object_type.model_fields
    return wire_key(field_name, object_type if declared else None)


_FROZEN = ConfigDict(frozen=True, strict=True, arbitrary_types_allowed=True)


class FieldValue(BaseModel):
    """A distinguisher read from the payload: one field holding one value.

    Construction fails unless *value* is a member of the enum that
    *field* is declared with on *object_type* (MSM-08-002).

    Attributes:
        object_type: The class of the activity's ``object`` that carries the
            field, e.g. ``ParticipantStatus``.
        field: The field name, e.g. ``"vf_state"``.
        value: The enum member the occasion's payload carries.
    """

    model_config = _FROZEN

    object_type: type
    field: NonEmptyString
    value: Enum

    @model_validator(mode="after")
    def _value_is_a_member_of_the_field_enum(self) -> "FieldValue":
        enums = _enum_classes(_field_annotation(self.object_type, self.field))
        if not enums:
            raise ValueError(
                f"{self.object_type.__name__}.{self.field} is not typed by an"
                " enum, so it cannot distinguish an occasion (MSM-08-002)"
            )
        if not any(isinstance(self.value, enum) for enum in enums):
            names = ", ".join(enum.__name__ for enum in enums)
            raise ValueError(
                f"{self.value!r} is not a member of {names}, the enum of"
                f" {self.object_type.__name__}.{self.field} (MSM-08-002)"
            )
        return self

    def read(self, carrier: object) -> object:
        """Return the value *carrier* holds in this distinguisher's field.

        A status dimension field is read as its ``state``, the value it
        travels as (ARCH-25-005, ADR-0099), so it compares to
        :attr:`value`.
        """
        held = getattr(carrier, self.field)
        if is_dimension_model(type(held)):
            return getattr(held, DIMENSION_STATE_FIELD)
        return held


class StateContext(BaseModel):
    """A distinguisher read from the receiver's state, not the payload.

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


Distinguisher = FieldValue | StateContext


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
            occasions, when it has any.
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
    "StateContext",
    "wire_spelling",
]
