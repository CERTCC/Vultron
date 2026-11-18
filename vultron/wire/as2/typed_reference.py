#!/usr/bin/env python
"""The typed reference: an inline object that names an object by type.

ADR-0198: an object slot a receiver reads holds a whole object, a typed
reference or a URI, and the shape of the keys alone tells them apart.  An
inline object with exactly an ``id`` and a ``type`` (and optionally an AS2
``preview``) is a typed reference.  It names an object of that type and claims
nothing else about it (MV-10-011).  Any other key makes the object a whole
object, which its class validates in full and refuses when it fails
(MV-04-003).

This module is the one place that reads that shape:

- :func:`is_typed_reference_shape` answers whether a received mapping is a
  typed reference (defined in :mod:`vultron.wire.as2.reference_shape`, so
  the vocabulary's inbound validator can ask it, and re-exported here), and
  :func:`carries_preview` whether it carries a preview;
- :func:`refuse_undefined_preview` refuses a preview for a type that defines
  none, or one that is not its type's preview (MV-10-012);
- :class:`as_TypedReference` is what the parser reads one as, for every type
  that has no reference form of its own (:func:`reads_as_typed_reference`);
- :func:`is_previewed_reference` answers whether a parsed object is a typed
  reference carrying a preview, which a receiver reads as received: never
  expanded into the object it names, never fetched, and never a replica's
  source (MV-10-011, ADR-0205);
- :func:`case_reference` builds the typed reference a participant's act on a
  case names it by, and :func:`is_case_reference` recognizes one (ADR-0165).

A typed reference shares the ``type`` of the object it names, so it claims no
``WIRE_TYPE_MAP`` key: the shape, not the registry, tells it from a whole
object of that type (VM-01-017).  An actor reference keeps the form it had
before this rule generalized it: the actor's own class carrying only its
``id`` (AKM-05-017, ADR-0159).  A collection carrying only its ``id`` is the
address of an actor's endpoint (AKM-02-006), and a ``CasePreview`` keeps its
own shape and position rules (MV-10-001, MV-10-002).  A case reference names a
case by exactly its ``id`` and ``type`` (ADR-0165); one that also carries the
case's preview is a previewed reference, read by the preview's rules
(ADR-0205), and is not a case reference.
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

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Any, ClassVar, TypeGuard

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vultron.core.models.actor import CoreActor
from vultron.core.models.embargo_event import EmbargoEvent as CoreEmbargoEvent
from vultron.core.models.enums import VultronObjectType as VO_type
from vultron.primitives import NonEmptyString
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.reference_shape import (
    TYPED_REFERENCE_KEYS,
    is_typed_reference_shape,
)
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.collections import as_Collection
from vultron.wire.as2.vocab.base.objects.object_types import as_Event
from vultron.wire.as2.vocab.base.registry import (
    resolve_wire_type,
    resolved_wire_type_name,
)
from vultron.wire.as2.vocab.objects.case_preview import as_CasePreview

#: The key a typed reference carries its preview under.
PREVIEW_KEY = "preview"

#: The preview the protocol defines for each type, by the type's wire name
#: (MV-10-012, ADR-0198).  A case's preview is ``CasePreview``, carrying what
#: an invitee decides on before it may see the case (CM-17-010, ADR-0205).
#: A typed reference of any other type that carries a ``preview`` is
#: refused, as is a case reference whose preview is not an inline
#: ``CasePreview``.
#: Previews beyond the case's are #6257.
DEFINED_PREVIEWS: Mapping[str, type[BaseModel]] = MappingProxyType(
    {"VulnerabilityCase": as_CasePreview}
)

#: The types whose preview the protocol defines (MV-10-012, ADR-0198).
TYPES_WITH_DEFINED_PREVIEW: frozenset[str] = frozenset(DEFINED_PREVIEWS)


def carries_preview(value: Mapping[str, Any]) -> bool:
    """Whether the typed reference *value* carries a ``preview``."""
    return PREVIEW_KEY in value


def refuse_undefined_preview(value: Mapping[str, Any], path: str = "") -> None:
    """Refuse a typed reference whose preview its type does not define
    (MV-10-012).

    A preview is a limited view of an object for a recipient that may not
    hold it, and what it may carry is decided per type (ADR-0193, ADR-0198).
    A preview of a type that defines none would be read by no rule, so it is
    refused rather than carried unchecked.  So is a preview that is not its
    type's preview carried inline (:data:`DEFINED_PREVIEWS`): the recipient
    of a preview may not hold the object, nor be entitled to fetch it, so a
    preview given by URI tells it nothing.  Returns when *value* is not a
    typed reference carrying a preview, or the preview is its type's.

    Args:
        value: The received inline mapping.
        path: Dotted position of *value* in the activity body, which the
            refusal names.

    Raises:
        VultronParseValidationError: When the preview is undefined for the
            reference's type.
    """
    if not (is_typed_reference_shape(value) and carries_preview(value)):
        return
    type_name = resolved_wire_type_name(value.get("type"), include_core=True)
    where = f" at {path!r}" if path else ""
    preview_cls = DEFINED_PREVIEWS.get(type_name or "")
    if preview_cls is None:
        raise VultronParseValidationError(
            f"Typed reference{where} carries a 'preview', but no preview is"
            f" defined for type {value.get('type')!r} (MV-10-012). Send the"
            " reference as exactly its 'id' and 'type', or the whole object."
        )
    if _is_inline_object_of(value[PREVIEW_KEY], preview_cls):
        return
    raise VultronParseValidationError(
        f"Typed reference{where} carries a 'preview' that is not a"
        f" {type_name}'s preview: a {type_name} reference's preview is an"
        f" inline {_wire_name(preview_cls)} (MV-10-012, ADR-0205)."
    )


def _is_inline_object_of(value: object, cls: type[BaseModel]) -> bool:
    """Whether *value* is an inline object of class *cls*.

    The partition asks this of the received mapping, and the parser's
    expansion, which validates nested objects first, of the object the
    mapping became.
    """
    if isinstance(value, cls):
        return True
    if not isinstance(value, Mapping):
        return False
    try:
        return resolve_wire_type(value.get("type")) is cls
    except KeyError:
        return False


def _wire_name(cls: type[BaseModel]) -> str:
    """The wire ``type`` of *cls*, a defined preview's pinned ``type_``."""
    return str(cls.model_fields["type_"].default)


def reads_as_typed_reference(
    value: Mapping[str, Any], cls: type[BaseModel] | None
) -> bool:
    """Whether the parser reads *value*, of resolved class *cls*, as an
    :class:`as_TypedReference`.

    True for a typed reference shape whose class has no reference form of
    its own.  An actor's class is its actor reference (AKM-05-017), a
    collection naming only its ``id`` is an endpoint's address, and a
    ``Link`` is not an object.  A ``CasePreview`` keeps its own rules
    (MV-10-001).
    A case is read here like any other type: its ``{id, type}`` shape is the
    case reference (ADR-0165).
    """
    if cls is None or not is_typed_reference_shape(value):
        return False
    return not issubclass(
        cls,
        (
            as_Actor,
            CoreActor,
            as_Collection,
            as_Link,
            as_CasePreview,
        ),
    )


class as_TypedReference(as_Object):
    """An object named by typed reference: exactly its ``id`` and ``type``.

    The parser reads an inline ``{id, type}`` object as this, never as an
    object of the class its ``type`` names (MV-10-011, ADR-0198), so no field
    default of that class runs for it: a ``CaseParticipant`` reference gains
    no invented status (#5265).  Its ``type`` routes the activity as a whole
    object's would (SE-01-002).  It is never the object a handler reads:
    rehydration puts the object the receiver holds in its place, or reduces
    it to its bare id when the receiver holds none, so the inbox fetches the
    object first (AKM-05-007, AKM-05-010).  A case reference
    (:func:`is_case_reference`) is the exception: rehydration leaves it as
    it arrived and no fetch is named for it, because the handler reads the
    case from the receiver's own store and refuses one it lacks (AKM-03-006,
    ADR-0165).

    It claims no ``WIRE_TYPE_MAP`` key: its ``type`` is the referenced
    object's, any type at all, so it declares no ``Literal`` (VM-01-017).

    It may carry its type's preview, which only a case defines: the case
    stub (MV-10-012, ADR-0205).  A reference carrying a preview is read as
    received, never replaced by the object it names
    (:func:`is_previewed_reference`).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type_: NonEmptyString = Field(  # type: ignore[assignment]
        ..., validation_alias="type", serialization_alias="type"
    )
    id_: NonEmptyString = Field(
        ..., validation_alias="id", serialization_alias="id"
    )
    # Nobody asserted a time for a reference, so none is stamped from this
    # process's clock (AKM-02-006, ADR-0159).  A reference is no whole
    # object, so a received one carries no time (CLP-15-011).
    published: datetime | None = None
    updated: datetime | None = None
    _received_without_published: ClassVar[bool] = True
    # The one defined preview (DEFINED_PREVIEWS, which a test holds to this
    # annotation); the parser refuses any other before this class reads it
    # (MV-10-012).
    preview: as_CasePreview | None = None  # type: ignore[assignment]

    @model_validator(mode="after")
    def _preview_is_its_types(self) -> as_TypedReference:
        """Refuse a preview its type does not define (MV-10-012).

        The parser refuses an undefined preview before this runs, but a
        stored row is read without the parser, so the class holds the rule
        itself.  The preview names no object of its own: the reference's
        ``id`` is the object it previews (ADR-0205).
        """
        if self.preview is None:
            return self
        type_name = resolved_wire_type_name(self.type_, include_core=True)
        defined = DEFINED_PREVIEWS.get(type_name or "")
        if defined is None or type(self.preview) is not defined:
            # Pydantic reports a ValueError raised here as a validation error.
            raise ValueError(
                f"a {self.type_} reference's preview is not that type's"
                " defined preview (MV-10-012, ADR-0205)"
            )
        return self


def is_previewed_reference(value: object) -> TypeGuard[as_TypedReference]:
    """Whether *value* is a typed reference that carries a preview.

    A receiver reads such a reference as received (MV-10-011, ADR-0205).
    The preview is a limited view for a recipient not yet entitled to the
    object, and an activity carrying it means something other than one
    carrying the whole object.  So the reference is never replaced by the
    object the receiver holds, never reduced to a bare id for the inbox to
    fetch, and satisfies only a pattern that asks for that form
    (SE-01-009), so no replica is seeded or updated from it.
    """
    return isinstance(value, as_TypedReference) and value.preview is not None


def case_reference(case_id: str) -> as_TypedReference:
    """Return the typed reference that names the case *case_id*.

    A participant's ``Join``, ``Ignore`` and ``Leave`` of a case and the
    ownership-transfer ``Offer`` name the case by this reference rather than
    carry a copy of it (AKM-03-003, ADR-0165).
    """
    return as_TypedReference(
        type_=VO_type.VULNERABILITY_CASE.value, id_=case_id
    )


def is_case_reference(value: object) -> bool:
    """Whether *value* is a case reference: exactly a case's id and type.

    A participant's act on a case names it this way (ADR-0165).  A typed
    reference to a case that carries the case's preview is not one: it is a
    previewed reference (:func:`is_previewed_reference`, ADR-0205).
    """
    return (
        isinstance(value, as_TypedReference)
        and value.type_ == VO_type.VULNERABILITY_CASE
        and value.preview is None
    )


#: Core classes that are a kind of an AS2 base type without subclassing its
#: wire class (ADR-0034, ADR-0099): a core actor is an ``Actor``, and the
#: core ``EmbargoEvent`` is an ``Event``.
_CORE_KINDS: tuple[tuple[type[BaseModel], type[BaseModel]], ...] = (
    (as_Actor, CoreActor),
    (as_Event, CoreEmbargoEvent),
)


def is_of_kind(cls: type, kind: type) -> bool:
    """Whether an object of class *cls* is an object of type *kind*.

    The one rule a pattern routing a reference and rehydration resolving it
    both ask (MV-10-011): a subclass of *kind*, or a core class that is a
    kind of *kind* without subclassing it (``_CORE_KINDS``), so a core
    ``EmbargoEvent`` is an ``Event`` and a core actor an ``Actor``.
    """
    if issubclass(cls, kind):
        return True
    return any(
        issubclass(base, kind) and issubclass(cls, core)
        for base, core in _CORE_KINDS
    )


def class_named_by(type_value: object) -> type[BaseModel] | None:
    """The wire class a received ``type`` value names, or ``None`` if unknown.

    A wire-only lookup (VM-06-013): a core class name such as ``CoreActor``
    is not an AS2 ``type``, so it names no class here.
    """
    try:
        return resolve_wire_type(type_value)
    except KeyError:
        return None


def referenced_class(reference: as_TypedReference) -> type[BaseModel] | None:
    """The class of the object *reference* names, or ``None`` if unknown.

    A pattern routes a typed reference by this class as it routes a whole
    object by its own (MV-10-011), so a reference to an ``EmbargoEvent``
    satisfies a pattern that asks for any ``Event``.
    """
    return class_named_by(reference.type_)


__all__ = [
    "DEFINED_PREVIEWS",
    "PREVIEW_KEY",
    "TYPED_REFERENCE_KEYS",
    "TYPES_WITH_DEFINED_PREVIEW",
    "as_TypedReference",
    "carries_preview",
    "case_reference",
    "class_named_by",
    "is_case_reference",
    "is_of_kind",
    "is_previewed_reference",
    "is_typed_reference_shape",
    "reads_as_typed_reference",
    "referenced_class",
    "refuse_undefined_preview",
]
