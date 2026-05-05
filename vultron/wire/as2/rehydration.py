#!/usr/bin/env python

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

"""
Wire-layer object rehydration utilities.

``rehydrate`` converts a loosely-typed ``as_Object`` (or a string ID reference)
into the correct wire-vocabulary subclass.  Callers MUST pass the active
``DataLayer`` instance via the *dl* parameter so that string ID references can
be resolved without importing a concrete adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError

from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

if TYPE_CHECKING:
    from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)

MAX_REHYDRATION_DEPTH = 5


def _resolve_string_id(obj_id: str, dl: DataLayer) -> as_Object:
    """Resolve a string ID reference to an ``as_Object`` via the data layer.

    Args:
        obj_id: The string ID to resolve.
        dl: DataLayer used for lookup.

    Returns:
        The resolved ``as_Object``.

    Raises:
        ValueError: If the ID cannot be resolved or resolves to an unexpected type.
    """
    logger.debug("Rehydrating string ID '%s' via provided DataLayer.", obj_id)
    resolved = dl.read(obj_id)
    if resolved is None:
        raise ValueError(f"Object '{obj_id}' not found in data layer")
    if not isinstance(resolved, as_Object):
        raise ValueError(
            f"Object '{obj_id}' resolved to unsupported type "
            f"{type(resolved).__name__}"
        )
    logger.debug("String ID '%s' resolved to %s.", obj_id, type(resolved))
    return resolved


def _rehydrate_nested_object_field(
    obj: as_Object, dl: DataLayer, depth: int
) -> as_Object | None:
    """Rehydrate the nested ``object_`` field of an ``as_Object`` in place.

    If the field is ``None``, raises ``ValueError``.  If rehydration of the
    nested object fails (e.g. remote federated object), logs a debug message
    and returns ``None`` so the caller keeps the original reference.

    Args:
        obj: Object whose ``object_`` field should be rehydrated.
        dl: DataLayer passed through to recursive ``rehydrate`` calls.
        depth: Current recursion depth.

    Returns:
        The rehydrated nested object, or ``None`` if rehydration was skipped.

    Raises:
        ValueError: If ``obj.object_`` is ``None``.
    """
    obj_with_object = cast(Any, obj)
    if obj_with_object.object_ is None:
        logger.error("'object_' field is None in %s.", obj.type_)
        raise ValueError(f"'object_' field is None in {obj.type_}")
    logger.debug("Rehydrating nested 'object_' of %s.", obj.type_)
    try:
        rehydrated_nested = rehydrate(
            obj_with_object.object_, dl=dl, depth=depth + 1
        )
        obj_with_object.object_ = rehydrated_nested
        return rehydrated_nested
    except ValueError:
        # Nested object not found in the local DataLayer — common in
        # federated scenarios where objects live on remote containers.
        # Keep the original ID string reference; pattern matching
        # treats string values as "conservatively allowed" (see
        # ActivityPattern._match_field), and use cases handle the
        # missing object gracefully.
        logger.debug(
            "Could not rehydrate nested 'object_' of %s; "
            "keeping original reference.",
            obj.type_,
        )
        return None


def _cast_to_vocabulary_type(obj: as_Object) -> as_Object:
    """Look up the correct vocabulary class for *obj* and rehydrate if needed.

    Args:
        obj: Object to cast to its canonical vocabulary type.

    Returns:
        The object cast (or already typed) to the correct subclass.

    Raises:
        ValueError: If ``obj`` lacks a ``type_`` attribute or the value is ``None``,
            or if rehydration yields an unexpected type.
        KeyError: If the type string is not registered in the vocabulary.
        ValidationError: If Pydantic validation of the rehydrated object fails.
    """
    if not hasattr(obj, "type_"):
        logger.error("Object %s has no 'type_' attribute.", obj)
        raise ValueError(f"Object {obj} has no 'type_' attribute.")
    if obj.type_ is None:
        raise ValueError(f"Object {obj} has no 'type_' value.")
    try:
        cls = find_in_vocabulary(obj.type_)
    except KeyError:
        logger.error("Unknown object type: %s.", obj.type_)
        raise
    if isinstance(obj, cls):
        logger.debug(
            "Object already rehydrated as '%s', skipping.",
            obj.__class__.__name__,
        )
        return cast(as_Object, obj)
    logger.debug(
        "Rehydrating to class %s for type %s.", cls.__name__, obj.type_
    )
    try:
        rehydrated = cls.model_validate(obj.model_dump())
    except ValidationError:
        logger.error("%s validation failed on %s.", cls.__name__, obj)
        raise
    if not isinstance(rehydrated, as_Object):
        raise ValueError(
            f"Rehydration of {obj.type_} produced unsupported type "
            f"{type(rehydrated).__name__}"
        )
    return cast(as_Object, rehydrated)


def rehydrate(
    obj: as_Object | str, dl: DataLayer, depth: int = 0
) -> as_Object:
    """Recursively rehydrate an object if needed.

    Performs depth-first rehydration up to ``MAX_REHYDRATION_DEPTH`` levels.

    Args:
        obj: The object (or string ID) to rehydrate.
        dl: DataLayer used to resolve string ID references.
        depth: Current recursion depth (callers should not set this).

    Returns:
        The rehydrated object of the correct wire-vocabulary subclass.

    Raises:
        RecursionError: If the maximum rehydration depth is exceeded.
        ValueError: If the object cannot be found or has an invalid structure.
        KeyError: If the object type is unrecognised in the vocabulary.
        ValidationError: If Pydantic validation of the rehydrated object fails.
    """
    if depth > MAX_REHYDRATION_DEPTH:
        raise RecursionError(
            f"Maximum rehydration depth of {MAX_REHYDRATION_DEPTH} exceeded."
        )

    if isinstance(obj, str):
        obj = _resolve_string_id(obj, dl)

    rehydrated_nested = None
    if hasattr(obj, "object_"):
        rehydrated_nested = _rehydrate_nested_object_field(obj, dl, depth)

    rehydrated = _cast_to_vocabulary_type(obj)

    if rehydrated_nested is not None and hasattr(rehydrated, "object_"):
        cast(Any, rehydrated).object_ = rehydrated_nested
        logger.debug(
            "Preserved rehydrated nested object of type %s.",
            rehydrated_nested.__class__.__name__,
        )

    return cast(as_Object, rehydrated)
