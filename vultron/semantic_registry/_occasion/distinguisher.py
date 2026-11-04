"""Distinguishers: what tells one occasion of an entry from another
(field value, state context, sender standing; MSM-08-002, MSM-08-011)."""

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

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
)
from vultron.core.models.dimensions import (
    DIMENSION_STATE_FIELD,
    is_dimension_model,
)
from vultron.primitives import NonEmptyString
from vultron.semantic_registry._occasion.annotations import (
    _embedded_model,
    _enum_classes,
    _field_annotation,
)

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
