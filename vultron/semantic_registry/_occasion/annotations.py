"""Field-annotation introspection the occasion distinguishers validate
against, and the wire spelling of a distinguishing field (MSM-08-002)."""

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
from enum import Enum

from pydantic import BaseModel

from vultron.core.models.dimensions import (
    DIMENSION_STATE_FIELD,
    is_dimension_model,
)
from vultron.core.models.wire_keys import wire_key


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
