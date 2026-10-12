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
    """The how-to guides an occasion links to, as ``docs/``-relative paths."""

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


_ANCHOR_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
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

    A field may be a declared Pydantic field or a read property; the flat
    status views (``vf_state``, ``pxa_state``) are properties over their
    dimension objects (ADR-0099 detail 5).
    """
    attribute = getattr(object_type, field_name, None)
    if isinstance(attribute, property) and attribute.fget is not None:
        hints = typing.get_type_hints(attribute.fget)
        if "return" in hints:
            return hints["return"]
    model_fields = getattr(object_type, "model_fields", {})
    if field_name in model_fields:
        return model_fields[field_name].annotation
    raise ValueError(
        f"{object_type.__name__} has no typed field {field_name!r}"
    )


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
        description: One or two sentences on what the activity does.
        example: Name of the ``vocab_examples`` function that builds this
            occasion's example (MSM-08-003).
        distinguisher: What tells this occasion apart from the entry's other
            occasions, when it has any.
        howto: The how-to guide whose steps send it.
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
    anchor: Annotated[str, Field(pattern=_ANCHOR_PATTERN)]
    description: NonEmptyString
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


__all__ = [
    "Distinguisher",
    "FieldValue",
    "HowToGuide",
    "MessagePage",
    "Occasion",
    "ProtocolShorthand",
    "StateContext",
]
