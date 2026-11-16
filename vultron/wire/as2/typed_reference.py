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
  typed reference, and :func:`carries_preview` whether it carries a preview;
- :func:`refuse_undefined_preview` refuses a preview for a type that defines
  none (MV-10-012);
- :class:`as_TypedReference` is what the parser reads one as, for every type
  that has no reference form of its own (:func:`reads_as_typed_reference`).

Two types keep the reference forms they had before this rule generalized
them: an actor reference is the actor's own class carrying only its ``id``
(AKM-05-017, ADR-0159), and a case reference is
:class:`~vultron.wire.as2.vocab.objects.vulnerability_case.as_VulnerabilityCaseReference`
(ADR-0165).  A collection carrying only its ``id`` is the address of an
actor's endpoint (AKM-02-006), and a case stub keeps its own shape and
position rules (MV-10-001, MV-10-002) until the stub moves into a case
reference's ``preview`` (ADR-0205).
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
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vultron.core.models.actor import CoreActor
from vultron.primitives import NonEmptyString
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.collections import as_Collection
from vultron.wire.as2.vocab.base.registry import (
    resolve_wire_type,
    resolved_wire_type_name,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseReference,
    as_VulnerabilityCaseStub,
)

#: The keys a typed reference may carry: its ``id`` and ``type``, the JSON-LD
#: ``@context`` any object may cite, and an AS2 ``preview`` (MV-10-011).
TYPED_REFERENCE_KEYS: frozenset[str] = frozenset(
    {"@context", "id", "type", "preview"}
)

#: The key a typed reference carries its preview under.
PREVIEW_KEY = "preview"

#: The types whose preview the protocol defines (MV-10-012, ADR-0198).  A
#: typed reference of any other type that carries a ``preview`` is refused.
#: None is defined yet: the case's preview is the work of ADR-0205 (#6244),
#: and previews beyond it are #6257.
TYPES_WITH_DEFINED_PREVIEW: frozenset[str] = frozenset()


def is_typed_reference_shape(value: Mapping[str, Any]) -> bool:
    """Whether the received *value* is a typed reference (MV-10-011).

    An ``id``, a ``type``, and no other key but ``@context`` and ``preview``.
    The shape alone decides, whatever the type: a mapping with any other key
    is a whole object, which its class judges (ADR-0198).
    """
    return (
        "id" in value
        and "type" in value
        and set(value) <= TYPED_REFERENCE_KEYS
    )


def carries_preview(value: Mapping[str, Any]) -> bool:
    """Whether the typed reference *value* carries a ``preview``."""
    return PREVIEW_KEY in value


def refuse_undefined_preview(value: Mapping[str, Any], path: str = "") -> None:
    """Refuse a typed reference whose type defines no preview (MV-10-012).

    A preview is a limited view of an object for a recipient that may not
    hold it, and what it may carry is decided per type (ADR-0193, ADR-0198).
    A preview of a type that defines none would be read by no rule, so it is
    refused rather than carried unchecked.  Returns when *value* is not a
    typed reference carrying a preview, or its type defines one.

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
    if type_name in TYPES_WITH_DEFINED_PREVIEW:
        return
    where = f" at {path!r}" if path else ""
    raise VultronParseValidationError(
        f"Typed reference{where} carries a 'preview', but no preview is"
        f" defined for type {value.get('type')!r} (MV-10-012). Send the"
        " reference as exactly its 'id' and 'type', or the whole object."
    )


def reads_as_typed_reference(
    value: Mapping[str, Any], cls: type[BaseModel] | None
) -> bool:
    """Whether the parser reads *value*, of resolved class *cls*, as an
    :class:`as_TypedReference`.

    True for a typed reference shape whose class has no reference form of
    its own.  An actor's class is its actor reference (AKM-05-017), a
    collection naming only its ``id`` is an endpoint's address, and a
    ``Link`` is not an object; the case's reference is resolved before this
    is asked (ADR-0165).  A case stub keeps its own rules (MV-10-001).
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
            as_VulnerabilityCaseReference,
            as_VulnerabilityCaseStub,
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
    object first (AKM-05-007, AKM-05-010).

    It claims no ``WIRE_TYPE_MAP`` key: its ``type`` is the referenced
    object's, any type at all, so it declares no ``Literal``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type_: NonEmptyString = Field(  # type: ignore[assignment]
        ..., validation_alias="type", serialization_alias="type"
    )
    id_: NonEmptyString = Field(
        ..., validation_alias="id", serialization_alias="id"
    )
    # Nobody asserted a time for a reference, so none is stamped from this
    # process's clock (AKM-02-006, ADR-0159).
    published: datetime | None = None
    updated: datetime | None = None


def referenced_class(reference: as_TypedReference) -> type[BaseModel] | None:
    """The class of the object *reference* names, or ``None`` if unknown.

    A pattern routes a typed reference by this class as it routes a whole
    object by its own (MV-10-011), so a reference to an ``EmbargoEvent``
    satisfies a pattern that asks for any ``Event``.
    """
    try:
        return resolve_wire_type(reference.type_)
    except KeyError:
        return None


__all__ = [
    "PREVIEW_KEY",
    "TYPED_REFERENCE_KEYS",
    "TYPES_WITH_DEFINED_PREVIEW",
    "as_TypedReference",
    "carries_preview",
    "is_typed_reference_shape",
    "reads_as_typed_reference",
    "referenced_class",
    "refuse_undefined_preview",
]
